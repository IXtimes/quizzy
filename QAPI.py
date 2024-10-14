import os
import json
import re
import sys
import time
from openai import OpenAI
import requests
from prompts import *
import random
import threading

CONTEXT_CUTOFF = 500
MAX_THREADS = 5
REFINEMENT_THREADS = 5

class RandomNumberGenerator:
    def __init__(self):
        self.lock = threading.Lock()

    def generate_random_number(self):
        with self.lock:
            random_number = random.randint(1, 999999)
            return random_number

rand = RandomNumberGenerator()

def get_driver_function():
    print('''Select a driver function: 
          \t1. Test API Key
          \t2. Generate new question based off permutation
          \t3. Exit''')
    return int(input("?: "))

def construct_question_object(type, question = None, q_index = None, correct_answers = None, incorrect_answers = None, terms = None, guidelines = None, format = None, language = None, forced = None, explaination = None):
    # create an empty dictionary to represent this question
    built_question = {}
    
    # ensure we have a question text and q_index, otherwise fail immediately
    if question is None or q_index is None:
        print("Failed to build question due to illegal input!")
        return None
    
    # pass q_index and question to field
    built_question['Q'] = q_index
    built_question['Question'] = question
    
    # switch on the question type
    match type:
        case "Multiple Choice":
            built_question['Type'] = "MC"
            
            # iterate and add the correct answers and incorrect answers
            for i, content in enumerate(correct_answers):
                built_question["C" + str(i)] = content
            for i, content in enumerate(incorrect_answers):
                built_question["A" + str(i)] = content
        case "Term-Definition":
            built_question['Type'] = "TD"
            
            # iterate over term definition pairs and add them to the question
            for i, (term, definition) in enumerate(terms):
                built_question["T" + str(i)] = term
                built_question["D" + str(i)] = definition
        case "Essay":
            built_question['Type'] = "Ess"
            
            # pass fields for guidelines and format
            built_question['Guidelines'] = guidelines
            built_question['Format'] = str(format)
            
            # if the format was 1, also pass the language
            built_question['Language'] = language if format == 1 else "N/A"
        case _:
            print("Failed to build question due to illegal input!")
            return None
                
    # pass if the question is forced to display in some state
    built_question['Forced'] = str(forced) if not forced is None else "0"
    
    # if there is an explaination, pass that in
    if explaination is not None:
        built_question['Explaination'] = explaination
        
    # return the built question object
    return built_question
            
def get_question_from_user_input(index, force_valid_input = False):
    # ask initally for the type of question and question itself
    while True:
        type = input("Enter the question type: (Multiple Choice, Term-Definition, Essay) ")
        if type == "Multiple Choice" or type == "Term-Definition" or type == "Essay":
            break
    
    while True:
        print('''Select one of the following:
            \t1. The question can have FRQ responses
            \t2. The question NEVER has FRQ responses
            \t3. The question ALWAYS has FRQ responses''')
        replaced = int(input("?: ")) - 1
        if replaced < 3 and replaced > -1:
            break

    question = input("Enter the question, you may specify imbeds using ``` notation: ")
    
    match type:
        case "Multiple Choice":
            # iterate asking for correct answer choices until the user enters STOP
            correct_answers = []
            correct_count = 0
            while True:
                buffer = input("Enter a correct answer choice: (or STOP to move on) ")
                if buffer == "STOP" and (not force_valid_input or correct_count < 1):
                    break
                correct_count += 1
                correct_answers.append(buffer)
                
            # iterate asking for incorrect answer choices until the user enters STOP
            incorrect_answers = []
            incorrect_count = 0
            while True:
                buffer = input("Enter an incorrect answer choice: (or STOP to move on) ")
                if buffer == "STOP" and (not force_valid_input or incorrect_count < 1):
                    break
                incorrect_count += 1
                incorrect_answers.append(buffer)
                
            # generate and return the built question
            return construct_question_object(type, question, index, correct_answers=correct_answers, incorrect_answers=incorrect_answers, forced=replaced)
        
        case "Term-Definition":
            # iterate asking for term definition pairs
            pairs = []
            pair_count = 0
            while True:
                term = input("Enter a term: (or SKIP to skip this field) ")
                if not term == "SKIP" and not force_valid_input:
                    definition = input("Enter that term's definition: (or SKIP to skip this field) ")
                    if not force_valid_input:
                        pairs.append((term, definition if not definition == "SKIP" else ""))
                        pair_count += 1
                elif not force_valid_input:
                    definition = input("Enter a definition for whom we are missing the term: (or SKIP to move on) ")
                    if definition == "SKIP":
                        break
                    pairs.append(("", definition))
                elif force_valid_input and incorrect_count < 1:
                    if input("Please enter CONTINUE if you wish to move on: ") == "CONTINUE":
                        break
                    
            # generate and return the built question
            return construct_question_object(type, question, index, terms=pairs, forced=replaced)
        case "Essay":
            # get the guidelines for the question
            guidelines = input("Enter the grading guidelines for this question: ")
            
            # select the formatting criterion for which the question is graded
            while True:
                print('''Select one of the following:
                    \t1. The student's response is to be graded as if it was an explaination
                    \t2. The student's response is to be graded as if it were code
                    \t3. The student's response is to be graded as if it were a formal proof''')
                format = int(input("?: ")) - 1
                if format < 3 and format > -1:
                    break
                
            # ask for the language that the expected code is to be written in
            language = input("Enter the language you expect the student's response to be written in: ") if format == 1 else ""
            
            # generate and return the built question
            return construct_question_object(type, question, index, guidelines=guidelines, format=format, language=language, forced=replaced)
        case _:
            print("Failed to build question due to illegal input!")
            return None

def get_random_context_segment(context, cutoff):
    # split the context segment into words and randomly choose a segment of those words based on the cuttoff
    context_words = context.split(" ")
    start_point = random.choice(range(0, max(len(context_words) - cutoff, 1)))
    return " ".join(context_words[start_point:min(start_point+cutoff, len(context_words))]) + "\n"

def remove_backticked_imbeds(s):
    # split the input based on backticked imbeds
    imbeds = s.split('```')
    result = ""
    
    # iterate through the imbeds
    for i, chunk, in enumerate(imbeds):
        if i % 2 == 0:
            # not an embed, skip
            result += chunk
        else:
            # readd if not an image embed
            if not chunk.startswith("img:"):
                result += "```" + chunk + "```"
    
    return result

def get_image_embed_links_if_any(question):
    # Split the question content into chunks to search for the first img embed
    imbeds = question.split('```')
    
    for i, chunk in enumerate(imbeds):
        if i % 2 != 0:
            # determine what imbed we are using
            header = chunk.split(':')[0]
            if header == "img":
                # we are imbedding an image, remove header from string
                link = chunk[4:]
                
                # fetch the image using a request
                response = requests.get(link)
                
                # check if successful
                if response.status_code == 200:
                    # return link
                    return link
                else:
                    # return blank
                    return ""
                
    # return blank if no link is found
    return ""

def get_unique_permutations_in_question(question, domain, context, api_key, model, t_results = None):
    # generate MAX_THREADS permutations for the same question
    threads = []
    results = []
    for i in range(REFINEMENT_THREADS):
        threads.append(threading.Thread(target=seed_permutations_in_question, args=(question, domain, context, api_key, model, results)))
        threads[i].start()
        time.sleep(0.5)
    for i in range(REFINEMENT_THREADS):
        threads[i].join()
        
    # using the results array garnered, log and remove all duplicate results
    duplicates = []
    for i in range(len(results) - 1):
        if results[i] in results[i+1:]:
            if not results[i] in duplicates:
                duplicates.append(results[i])
                
    # return the list of unique results
    unique_datems = [result for result in results if result not in duplicates]
    if t_results is None:
        return unique_datems[random.randint(0, len(unique_datems) - 1)]
    else:
        t_results.append(unique_datems[random.randint(0, len(unique_datems) - 1)])

def seed_permutations_in_question(question, domain, context, api_key, model, t_results = None):
    # First retrieve an image embed if it exists
    img_link = get_image_embed_links_if_any(question)
    
    # Split the question content into chunks to search for the first img embed
    embeds = question.split('```')
    cut_segment = []
    blank_question = ""
    
    for i, chunk in enumerate(embeds):
        if i % 2 != 0:
            # determine what imbed we are using
            header = chunk.split(':')[0]
            if header == "prt":
                # this is a permutatable part, get the original text and add it to the cut segment
                cut_segment.append(chunk[4:])
                blank_question += "_" * len(chunk)
            else:
                # readd embed markings if not an image embed
                if not chunk.startswith("img:"):
                    blank_question += "```" + chunk + "```"
        else:
            # push chunk back to question string
            blank_question += chunk
                    
    # prompt to fill in the blanks of the question to generate a whole new question
    client = OpenAI(api_key=api_key)
    domain_c = "Domain: " + domain + "\n"
    context_c = "Context: " + get_random_context_segment(context, CONTEXT_CUTOFF) + "\n"
    model_c = "gpt-4o-mini" if model == '3.5' else "gpt-4o"
    question_c = blank_question + "\n"
    seed = rand.generate_random_number()
    
    response = client.chat.completions.create (
        model = model_c,
        presence_penalty= 2,
        seed= seed,
        messages = [
            {"role": "system", "content": SYSTEM_INTRO + REQUEST_EXAMPLE_FILL_IN_BLANKS + SYSTEM_CONCLUSION + (IMG_SPECIFICATION if img_link != "" else "")},
            {
                "role":"user",
                "content": [
                    {"type": "text", "text": domain_c + context_c + question_c + REQUEST_FILL_IN_BLANKS},
                    {"type": "image_url", "image_url": {
                        "url": img_link
                    }} 
                ] if img_link != "" else [
                    {"type": "text", "text": domain_c + context_c + question_c + REQUEST_FILL_IN_BLANKS}
                ]
            }
        ]
    )
    
    # parse the contents returned by the AI
    try:
        # cleanup the output
        lines = response.choices[0].message.content.split('\n')
        fills = []
        for i, line in enumerate(lines):
            # remove header tag and strip misc whitespace
            fills.append(line.strip()[(3 + i // 10):])
            
        # reparse the question with the blanks filled
        q_parts = re.split(r'_+', blank_question)
        complete_question = ""
        for part in q_parts:
            complete_question += part + (fills.pop(0) if len(fills) > 0 else "")
        
        if t_results is None:
            return complete_question
        else:
            t_results.append(complete_question)
    except Exception as e:
        print("Failed call to GPT!")
        if t_results is None:
            return None
        else:
            t_results.append(None)
    
def generate_explaination_for_question(question, domain, context, api_key):
    # test api key
    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "user", "content": "This is a test prompt, please respond with ONLY 'OK'"}
            ]
        )
        result = response.choices[0].message.content
    except Exception as e:
        return False

def test_api_key(api_key):
    # test api key
    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "user", "content": "This is a test prompt, please respond with ONLY 'OK'"}
            ]
        )
        result = response.choices[0].message.content
    except Exception as e:
        return False
    
    if not "OK" in result:
        return False
    return True

if __name__ == "__main__":
    driver_loop = True
    
    domain = input("Enter the domain segment: ")
    context_file = input("Enter the name of the file that contains the context segment: ")
    context = open(context_file, "r").read()
    model = "3.5"
    
    # Get API key from app
    try:
        # get the file path
        user_path = os.path.expanduser("~")
        directory = os.path.join(user_path, "IXSettings", "Quizzy", "quizzy.json")
        
        # open the settings file
        with open(directory, 'r') as file:
            json_settings = file.read()
            
        # convert JSON to dictionary
        py_obj = json.loads(json_settings)
        settings = dict(py_obj)
        success = True
    except Exception as e:
        # report, but we'd only get an exception if the settings file didnt exist or was tampered so we just wont fill the datems
        success = False
        
    if success:
        try:
            # write from dictionary to fields
            api_key = settings['API Key']
            print("Successfully grabbed API key")
        except Exception as e:
            # write from dictionary to fields
            api_key = "NaN"
            print("Failed to get API key, make sure its properly seeded in the Quizzy client!")
    
    print("\n=====================================================\n")
    while driver_loop:
        match get_driver_function():
            case 1:
                print("API key is valid!" if test_api_key(api_key) else "API key is INVALID!")
            case 2:
                question = get_question_from_user_input(0)
                n = int(input("How many questions do you wish to generate? "))
                threads = []
                results = []
                while n > 0:
                    for i in range(MAX_THREADS if n // MAX_THREADS > 0 else n):
                        threads.append(threading.Thread(target=get_unique_permutations_in_question, args=(question["Question"], domain, context, api_key, model, results)))
                        threads[i].start()
                        time.sleep(1)
                    for i in range(MAX_THREADS if n // MAX_THREADS > 0 else n):
                        threads[i].join()
                    for i in range(MAX_THREADS if n // MAX_THREADS > 0 else n):
                        print(results[i])
                    threads.clear()
                    results.clear()
                    n -= MAX_THREADS
            case 3:
                driver_loop = False