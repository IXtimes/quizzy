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

def get_driver_function():
    print('''Select a driver function: 
          \t1. Test API Key
          \t2. Write new question and auto-complete for missing content
          \t3. Generate new question based off permutation
          \t4. Exit''')
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
            for i, content in enumerate(correct_answers, 1):
                built_question["C" + str(i)] = content
            for i, content in enumerate(incorrect_answers, 1):
                built_question["A" + str(i)] = content
        case "Term-Definition":
            built_question['Type'] = "TD"
            
            # iterate over term definition pairs and add them to the question
            for i, (term, definition) in enumerate(terms, 1):
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

def generate_permutation_from_question(question, domain, context, api_key, model, t_results = None):
    # create a new question object
    new_question = {}
    
    # seed the question text with generated permutations (permutation questions dont have an index as they are not saved)
    new_question['Q'] = str(-1)
    new_question['Forced'] = str(1)
    new_question['Question'] = seed_permutations_in_question(question["Question"], domain, context, api_key, model)
    new_question['Type'] = question['Type']

    # from the new question header text, generate new answer choices that emulate the same pattern as the input
    match new_question['Type']:
        case "MC":
            fill_multiple_choice_options(new_question, domain, context, api_key, model)
        case 'TD':
            print("Not implemented")
        case 'Ess':
            print("Not implemented")

    # finally, generate the explaination for the question.
    generate_explaination_for_question(new_question, domain, context, api_key, model)

    # push results to threads, otherwise return
    if t_results is None:
        return new_question
    else:
        t_results.append(new_question)

def fill_multiple_choice_options(question, domain, context, api_key, model):
    # First retrieve an image embed if it exists
    img_link = get_image_embed_links_if_any(question["Question"])

    # initalize client and domain/context segments
    client = OpenAI(api_key=api_key)
    domain_c = "Domain: " + domain + "\n"
    context_c = "Context: " + get_random_context_segment(context, CONTEXT_CUTOFF) + "\n"
    model_c = "gpt-4o-mini" if model == '3.5' else "gpt-4o"

    # Determine what parts of the question we are missing
    # Generate the correct answer(s) and incorrect answer(s) if both are (effectively) missing
    if not "C1" in question.keys() and (not "A1" in question.keys() or ("A1" in question.keys() and not "A2" in question.keys())) :
        # Get the response from the GPT
        response = client.chat.completions.create (
            model = model_c,
            messages = [
                {"role": "system", "content": SYSTEM_INTRO + REQUEST_EXAMPLE_ALL_CHOICES + SYSTEM_CONCLUSION + (IMG_SPECIFICATION if img_link != "" else "")},
                {
                    "role":"user",
                    "content": [
                        {"type": "text", "text": domain_c + context_c + REQUEST_ALL_CHOICES + remove_backticked_imbeds(question["Question"])},
                        {"type": "image_url", "image_url": {
                            "url": img_link
                        }} 
                    ] if img_link != "" else [
                        {"type": "text", "text": domain_c + context_c + REQUEST_ALL_CHOICES + remove_backticked_imbeds(question["Question"])}
                    ]
                }
            ]
        )

        # Parse to get the correct and incorrect answers generated
        try:
            # iterate through the output
            lines = response.choices[0].message.content.split('\n')
            cur_key = ""
            num_cor = 0
            num_incor = 0 if not "A1" in question.keys() else 1
            for line in lines:
                # check if this line contains a correct answer
                if line.strip().startswith('C~'):
                    # get the new key
                    num_cor += 1
                    cur_key = "C" + str(num_cor)
                    
                    # set this line into the question dictionary
                    question[cur_key] = line[2:].strip()
                # check if this line contains a incorrect answer
                elif line.strip().startswith('I~'):
                    # get the new key
                    num_incor += 1
                    cur_key = "A" + str(num_incor)
                    
                    # set this line into the question dictionary
                    question[cur_key] = line[2:].strip()
                # otherwise is continuation of previous line
                else:
                    # if we enter here without a key, something went wrong
                    if cur_key == "":
                        raise Exception()
                    
                    # append this line to the previous on a newline
                    question[cur_key] = "\n" + line.strip()
        except Exception as e:
            # prompt error and prevent submit
            print("Failed call to GPT!")
        
            return
        
    
    # generate several incorrect answers if they are missing for several correct answers
    elif "C2" in question.keys() and not "A1" in question.keys():
        # get the required content for the prompt
        correct_answers_c = "Correct Answers: "
        correct_count = 0
        for key, value in question.items():
            if "C" in key:
                correct_answers_c += value + ", "
                correct_count += 1
        content = "Question: " + remove_backticked_imbeds(question['Question']) + "\n" + remove_backticked_imbeds(correct_answers_c) + "\n"

        # Get the response from the GPT
        response = client.chat.completions.create (
            model = model_c,
            messages = [
                {"role": "system", "content": SYSTEM_INTRO + REQUEST_EXAMPLE_INCORRECT_CHOICES_MULTIPLE_CORRECT + SYSTEM_CONCLUSION + (IMG_SPECIFICATION if img_link != "" else "")},
                {
                    "role":"user",
                    "content": [
                        {"type": "text", "text": domain_c + context_c + REQUEST_INCORRECT_CHOICES_MULTIPLE_CORRECT.replace("{X}", str(correct_count)) + content},
                        {"type": "image_url", "image_url": {
                            "url": img_link
                        }} 
                    ] if img_link != "" else [
                        {"type": "text", "text": domain_c + context_c + REQUEST_INCORRECT_CHOICES_MULTIPLE_CORRECT.replace("{X}", str(correct_count)) + content}
                    ]
                }
            ]
        )

        # Parse to get the correct and incorrect answers generated
        try:
            # iterate through the output
            lines = response.choices[0].message.content.split('\n')
            cur_key = ""
            num_cor = 0
            num_incor = 0
            for line in lines:
                # check if this line contains a incorrect answer
                if line.strip().startswith('I~'):
                    # get the new key
                    num_incor += 1
                    cur_key = "A" + str(num_incor)
                    
                    # set this line into the question dictionary
                    question[cur_key] = line[2:].strip()
                # otherwise is continuation of previous line
                else:
                    # if we enter here without a key, something went wrong
                    if cur_key == "":
                        raise Exception()
                    
                    # append this line to the previous on a newline
                    question[cur_key] = "\n" + line.strip()
        except Exception as e:
            # prompt error and prevent submit
            print("Failed call to GPT!")
        
            return
        
    # select a correct answer from the incorrect answers if enough incorrect answers are given.
    elif not "C1" in question.keys() and "A2" in question.keys():
        # First, generate the additional content
        answer_choices_c = "Answer Choices:\n"
        choice_num = 1
        for key, value in question.items():
            if "A" in key:
                answer_choices_c += "A" + str(choice_num) + "~ " + value + "\n"
                choice_num += 1
        content = "Question: " + remove_backticked_imbeds(question['Question']) + "\n" + answer_choices_c + "\n"

        # Get the response from the GPT
        response = client.chat.completions.create (
            model = model_c,
            messages = [
                {"role": "system", "content": SYSTEM_INTRO + REQUEST_EXAMPLE_SELECT_CORRECT_CHOICE + SYSTEM_CONCLUSION + (IMG_SPECIFICATION if img_link != "" else "")},
                {
                    "role":"user",
                    "content": [
                        {"type": "text", "text": domain_c + context_c + REQUEST_SELECT_CORRECT_CHOICE + content},
                        {"type": "image_url", "image_url": {
                            "url": img_link
                        }} 
                    ] if img_link != "" else [
                        {"type": "text", "text": domain_c + context_c + REQUEST_SELECT_CORRECT_CHOICE + content}
                    ]
                }
            ]
        )

        choices = []

        # parse
        print(response.choices[0].message.content.split('\n'))
        choice_num = 0
        for key, value in question.items():
            if "A" in key:
                choices.append(value)
                choice_num += 1
        while choice_num > 0:
            del question["A" + str(choice_num)]
            choice_num -= 1

        # Parse to get the correct and incorrect answers generated
        try:
            # iterate through the output
            lines = response.choices[0].message.content.split(',')
            cur_key = ""
            choice_num = len(lines)
            for i in range(len(lines) - 1, -1, -1):
                line = lines[i]
                # validate this choice
                if line.strip().startswith('A'):
                    # get the new key
                    cur_key = "C" + str(choice_num)
                    choice_num -= 1
                    
                    # set this line into the question dictionary
                    answer = int(line.strip()[1])
                    question[cur_key] = choices.pop(answer - 1)

                # otherwise is continuation of previous line
                else:
                    # if we enter here, we have a problem
                    raise Exception()
        except Exception as e:
            # prompt error and prevent submit
            print("Failed call to GPT!: " + str(e))
        
            return
        
        # push the remainder of the list as incorrect answer choices
        choice_num = 1
        for item in choices:
            question["A" + str(choice_num)] = item
            choice_num += 1

        
    # generate incorrect answers if they are missing for a single correct answer
    elif "C1" in question.keys() and not "A1" in question.keys():
        # first, generate additional content
        content = "Question: " + remove_backticked_imbeds(question["Question"]) + "\nCorrect Answer: " + remove_backticked_imbeds(question["C1"]) + "\n"

        # Get the response from the GPT
        response = client.chat.completions.create (
            model = model_c,
            messages = [
                {"role": "system", "content": SYSTEM_INTRO + REQUEST_EXAMPLE_INCORRECT_CHOICES_SINGLE_CORRECT + SYSTEM_CONCLUSION + (IMG_SPECIFICATION if img_link != "" else "")},
                {
                    "role":"user",
                    "content": [
                        {"type": "text", "text": domain_c + context_c + REQUEST_INCORRECT_CHOICES_SINGLE_CORRECT + content},
                        {"type": "image_url", "image_url": {
                            "url": img_link
                        }} 
                    ] if img_link != "" else [
                        {"type": "text", "text": domain_c + context_c + REQUEST_INCORRECT_CHOICES_SINGLE_CORRECT + content}
                    ]
                }
            ]
        )

        # Parse to get the correct and incorrect answers generated
        try:
            # iterate through the output
            lines = response.choices[0].message.content.split('\n')
            cur_key = ""
            num_cor = 0
            num_incor = 0
            for line in lines:
                # check if this line contains a incorrect answer
                if line.strip().startswith('I~'):
                    # get the new key
                    num_incor += 1
                    cur_key = "A" + str(num_incor)
                    
                    # set this line into the question dictionary
                    question[cur_key] = line[2:].strip()
                # otherwise is continuation of previous line
                else:
                    # if we enter here without a key, something went wrong
                    if cur_key == "":
                        raise Exception()
                    
                    # append this line to the previous on a newline
                    question[cur_key] = "\n" + line.strip()
        except Exception as e:
            # prompt error and prevent submit
            print("Failed call to GPT!")
        
            return

def seed_permutations_in_question(question_text, domain, context, api_key, model):
    # First retrieve an image embed if it exists
    img_link = get_image_embed_links_if_any(question_text)
    
    # Split the question content into chunks to search for the first img embed
    embeds = question_text.split('```')
    
    # Keep references for 2 seperate lists:
    segments = [] # Segments of the completed final string
    blank_defaults = [] # The original values of blanks, as well as the "type" of permutateable part they are
    blanks = [] # The blanks to slowly use to guide GPT to constructing a permutated question
    
    for i, chunk in enumerate(embeds):
        if i % 2 != 0:
            # determine what imbed we are using
            header = chunk.split(':')[0]
            if header == "prt":
                # this is a permutatable part, get the original text and add it to the cut segment
                blank_defaults.append((chunk[4:], "reg"))
                blanks.append("_" * len(chunk[4:]))
            elif header == "mathprt":
                # this is a MATH permutatable part, signify this in the tuple, otherwise its the same as a prt segment
                blank_defaults.append((chunk[8:], "math"))
                blanks.append("_" * len(chunk[8:]))
            else:
                # readd embed markings if not an image embed
                if not chunk.startswith("img:"):
                    segments.append("```" + chunk + "```")
        else:
            # log segment as is
            segments.append(chunk)
                    
    # initalize client and domain/context segments
    client = OpenAI(api_key=api_key)
    domain_c = "Domain: " + domain + "\n"
    context_c = "Context: " + get_random_context_segment(context, CONTEXT_CUTOFF) + "\n"
    model_c = "gpt-4o-mini" if model == '3.5' else "gpt-4o"
    
    # iterate getting responses from our client to fill in the blanks as they appear.
    # blanks already filled are considered a singular segment, the current blank appears blank and is requested to be filled, where all remaining blanks are filled with their default values.
    while not len(blanks) == 0:
        # sew a question together consisting of a blank where it first sees fit (between the first and second segment), followed by the remaining segments joined using the original default values as they appear
        question_c = ""
        comb_segments = (segments.pop(0), segments.pop(0))
        cur_blank = blank_defaults.pop(0)
        question_c = comb_segments[0] + blanks.pop(0) + comb_segments[1]
        for i, def_blank in enumerate(blank_defaults):
            if i < len(segments):
                question_c += def_blank[0] + segments[i]
            else:
                question_c += def_blank[0]
        size_c = "Please respond with options that are approximately " + str(len(cur_blank[0])) + " characters in length"
    
        # prompt the GPT to fill in the blank
        response = client.chat.completions.create (
            model = model_c,
            presence_penalty= 2,
            messages = [
                {"role": "system", "content": SYSTEM_INTRO + (REQUEST_EXAMPLE_FILL_IN_BLANKS if cur_blank[1] == "reg" else REQUEST_EXAMPLE_FILL_IN_MATH) + SYSTEM_CONCLUSION + (IMG_SPECIFICATION if img_link != "" else "")},
                {
                    "role":"user",
                    "content": [
                        {"type": "text", "text": domain_c + context_c + size_c + REQUEST_FILL_IN_BLANKS + remove_backticked_imbeds(question_text) + question_c},
                        {"type": "image_url", "image_url": {
                            "url": img_link
                        }} 
                    ] if img_link != "" else [
                        {"type": "text", "text": domain_c + context_c + size_c + REQUEST_FILL_IN_BLANKS + question_c}
                    ]
                }
            ]
        )
        
        try:
            # pick the option that is CLOSEST to the length of the blank
            options = response.choices[0].message.content.split('\n')
            distances = list(map(lambda x: abs(len(x.strip()) - len(cur_blank[0])), options))
            best_option = min(enumerate(distances), key=lambda x: x[1])[0]

            if cur_blank[1] == "reg":
                segments.insert(0, comb_segments[0] + options[best_option].strip() + comb_segments[1])
            else:
                segments.insert(0, comb_segments[0] + "```math:" + options[best_option].strip() + "```" + comb_segments[1])
        except Exception as e:
            print("Failed call to GPT!")
            return None

    # return the results
    return segments[0]
    
def generate_explaination_for_question(question, domain, context, api_key, model):
    # First retrieve an image embed if it exists
    img_link = get_image_embed_links_if_any(question["Question"])

    # initalize client and domain/context segments
    client = OpenAI(api_key=api_key)
    domain_c = "Domain: " + domain + "\n"
    context_c = "Context: " + get_random_context_segment(context, CONTEXT_CUTOFF) + "\n"
    model_c = "gpt-4o-mini" if model == '3.5' else "gpt-4o"

    # get the required content for the prompt
    correct_answers_c = "Correct Answers: "
    for key, value in question.items():
        if "C" in key:
            correct_answers_c += value + ", "
    content = "Question: " + remove_backticked_imbeds(question['Question']) + "\n" + remove_backticked_imbeds(correct_answers_c) + "\n"

    # prompt the GPT to write the explaination
    response = client.chat.completions.create (
        model = model_c,
        presence_penalty= 2,
        messages = [
            {"role": "system", "content": SYSTEM_INTRO + REQUEST_EXAMPLE_EXPLAINATIONS + SYSTEM_CONCLUSION + (IMG_SPECIFICATION if img_link != "" else "")},
            {
                "role":"user",
                "content": [
                    {"type": "text", "text": domain_c + context_c + REQUEST_EXPLAINATIONS + content},
                    {"type": "image_url", "image_url": {
                        "url": img_link
                    }} 
                ] if img_link != "" else [
                    {"type": "text", "text": domain_c + context_c + REQUEST_EXPLAINATIONS + content}
                ]
            }
        ]
    )

    # wrap in try/except to flag an error if the api fails
    try:
        # push to explaination
        question['Explaination'] = response.choices[0].message.content[2:].strip()
    except Exception as e:
        # prompt error and prevent submit
        print("Failed call to GPT!")
    
        return

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
                match question['Type']:
                    case 'MC':
                        fill_multiple_choice_options(question, domain, context, api_key, model)
                    case 'TD':
                        print("Not implemented")
                    case 'Ess':
                        print("Not implemented")

                generate_explaination_for_question(question, domain, context, api_key, model)

                print(question)
            case 3:
                question = get_question_from_user_input(0)
                n = int(input("How many questions do you wish to generate? "))
                threads = []
                results = []
                while n > 0:
                    for i in range(MAX_THREADS if n // MAX_THREADS > 0 else n):
                        threads.append(threading.Thread(target=generate_permutation_from_question, args=(question, domain, context, api_key, model, results)))
                        threads[i].start()
                        time.sleep(1)
                    for i in range(MAX_THREADS if n // MAX_THREADS > 0 else n):
                        threads[i].join()
                    for i in range(MAX_THREADS if n // MAX_THREADS > 0 else n):
                        print(results[i])
                    threads.clear()
                    results.clear()
                    n -= MAX_THREADS
            case 4:
                driver_loop = False