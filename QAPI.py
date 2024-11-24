import os
import json
import re
import sys
import time
from tkinter import filedialog
import Levenshtein as lev
from openai import OpenAI
import requests
from prompts import *
import random
import threading

CONTEXT_CUTOFF = 500
MAX_THREADS = 5
THREAD_SIZE = 1

def get_driver_function():
    print('''Select a driver function: 
          \t1. Test API Key
          \t2. Display question bank contents
          \t3. Load questions from a Quizzy file
          \t4. Write questions to a Quizzy file
          \t5. Write a new question and auto-complete for missing content
          \t6. Generate new question(s) based off written question w/ permutation
          \t7. Generate new question(s) off question bank sample
          \t8. Exit''')
    return int(input("?: "))

def validate_question_object(object):
    # ensure we have a question text and q_index, otherwise fail immediately
    if not 'Question' in object or not 'Q' in object:
        print("@FAIL (???): Object too corrupted to be a valid question object. Terminating...")
        return False
    
    # for debugging, grab the question's index
    q_index = object['Q']
    
    # determine the question's type
    try:
        if not 'Type' in object:
            print(f'@WARN ({q_index}): Question missing its type, defaulting to MC!')
            object['Type'] = 'MC'
        match object['Type']:
            case "MC":
                # count the incorrect and correct answers and ensure they enumerate correctly
                num_cor = 0
                max_cor = 0
                num_incor = 0
                max_incor = 0
                
                # iterate over the keys
                for key, ___ in object.items():
                    if not key.startswith(("C", "A")):
                        continue
                    k_prefix = key[0]
                    k_val = int(key[1:])
                    
                    # check for a correct key
                    if k_prefix == "C":
                        # count this key and log if this key is the largest found so far
                        num_cor += 1
                        max_cor = max(max_cor, k_val)
                    # check for a incorrect key
                    if k_prefix == "A":
                        # count this key and log if this key is the largest found so far
                        num_incor += 1
                        max_incor = max(max_incor, k_val)
                        
                # check if we are missing correct answers or incorrect answers entirely
                if num_cor == 0:
                    print(f'@FAIL ({q_index}): Question missing correct answers. Terminating...')
                    return False  
                if num_incor == 0:
                    print(f'@FAIL ({q_index}): Question missing incorrect answers. Terminating...')
                    return False  
                    
                # check if the counts match
                if num_cor != max_cor:
                    print(f'@FAIL ({q_index}): Question correct answer count does not match maximal index. Terminating...')
                    return False
                if num_incor != max_incor:
                    print(f'@FAIL ({q_index}): Question incorrect answer count does not match maximal index. Terminating...')
                    return False
                
                # check for illegal keys
                for key, ___ in object.items():
                    if key == "Type":
                        continue
                    if key.startswith(("T", "D", "Guidelines", "Format", "Language")):
                        print(f'@FAIL ({q_index}): MC question contains illegal key: "{key}" Terminating...')
                        return False
            case "TD":
                # count the terms and definitions and ensure they enumerate correctly
                num_terms = 0
                max_terms = 0
                num_defines = 0
                max_defines = 0
                
                # iterate over the keys
                for key, ___ in object.items():
                    if not key.startswith(("T", "D")) or key.startswith("Ty"):
                        continue
                    k_prefix = key[0]
                    k_val = int(key[1:])
                    
                    # check for a term key
                    if k_prefix == "T":
                        # count this key and log if this key is the largest found so far
                        num_terms += 1
                        max_terms = max(max_terms, k_val)
                    # check for a definition key
                    if k_prefix == "D":
                        # count this key and log if this key is the largest found so far
                        num_defines += 1
                        max_defines = max(max_defines, k_val)
                        
                # check if we are missing terms or definitions entirely
                if num_terms == 0:
                    print(f'@FAIL ({q_index}): Question missing terms. Terminating...')
                    return False  
                if num_defines == 0:
                    print(f'@FAIL ({q_index}): Question missing definitions. Terminating...')
                    return False  
                        
                # check if the counts match
                if num_terms != max_terms:
                    print(f'@FAIL ({q_index}): Question term count does not match maximal index. Terminating...')
                    return False
                if num_defines != max_defines:
                    print(f'@FAIL ({q_index}): Question definition count does not match maximal index. Terminating...')
                    return False
                
                # check for illegal keys
                for key, ___ in object.items():
                    if key == "Type":
                        continue
                    if key.startswith(("C", "A", "Guidelines", "Format", "Language")):
                        print(f'@FAIL ({q_index}): TD question contains illegal key: "{key}" Terminating...')
                        return False
            case "Ess":
                # fail if we lack guidelines
                if not "Guidelines" in object:
                    print(f'@FAIL ({q_index}): Essay question missing guidelines. Terminating...')
                    return False
                
                # check for format specification, and default to "1" if missing
                if not "Format" in object:
                    print(f'@WARN ({q_index}): Essay question missing format, defaulting to Essay (1)!')
                    object["Format"] = "1"
                
                # fail if format is "Code" and the language is not specified
                if not "Language" in object or (object["Format"] == "2" and object["Language"] == "N/A"):
                    print(f'@FAIL ({q_index}): Essay question missing language when "Code" was specified. Terminating...')
                    return False
                
                # check for illegal keys
                for key, ___ in object.items():
                    if key == "Type":
                        continue
                    if key.startswith(("T", "D", "A", "C")):
                        print(f'@FAIL ({q_index}): Essay question contains illegal key: "{key}" Terminating...')
                        return False
            case _:
                # fail for invalid type
                print(f'@FAIL ({q_index}): Question failed validation due to corrupted type: "{object["Type"]}". Terminating...')
                return False
                    
    except Exception as e:
        print(f'@FAIL ({q_index}): Question failed validation due to exception: "{e}". Terminating...')
        return False
    
    # check for a forced state, default to "Either" (0)
    if not "Forced" in object:
        print(f'@WARN ({q_index}): Question lacking "Forced" flag, defaulting to Either (0)!')
        object["Forced"] = "0"
        
    # check for an explaination, default to "No explaination was provided :("
    if not "Explaination" in object:
        print(f'@WARN ({q_index}): Question lacks explaination field, default provided!')
        object["Explaination"] = "No explaination was provided :("
        
    # if we make it here, then this question must be valid!
    return True                

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

def unscramble_matching(question, domain, context, api_key, model):
    pass

def fill_matching_options(question, scrambled, domain, context, api_key, model):
    # First retrieve an image embed if it exists
    img_link = get_image_embed_links_if_any(question["Question"])

    # initalize client and domain/context segments
    client = OpenAI(api_key=api_key)
    domain_c = "Domain: " + domain + "\n"
    context_c = "Context: " + get_random_context_segment(context, CONTEXT_CUTOFF) + "\n"
    model_c = "gpt-4o-mini" if model == '3.5' else "gpt-4o"

    # iterate through the term definition pairs of the question
    matchings = sum(1 for key in question if key.startswith("D"))
    terms = []
    definitions = []
    for i in range(matchings):
        if question["T" + str(i + 1)] != "":
            terms += question["T" + str(i + 1)]
        elif question["D" + str(i + 1)] != "":
            definitions += question["D" + str(i + 1)]
    terms = ", ".join(terms)
    definitions = ", ".join(definitions)
    
    # reiterate to fill in all blanks
    for i in range(matchings):
        # fill in the term if its missing given the context of the definition.
        print("T" + str(i + 1) + ", " + "D" + str(i+1))
        print(question["T" + str(i + 1)] + ", " + question["D" + str(i + 1)])
        if question["T" + str(i + 1)] == "" and question["D" + str(i + 1)] != "":
            # Get the response from the GPT
            response = client.chat.completions.create (
                model = model_c,
                messages = [
                    {"role": "system", "content": SYSTEM_INTRO + REQUEST_EXAMPLE_GENERATE_TERM + SYSTEM_CONCLUSION + (IMG_SPECIFICATION if img_link != "" else "")},
                    {
                        "role":"user",
                        "content": [
                            {"type": "text", "text": domain_c + context_c + REQUEST_GENERATE_TERM.replace("{X}", terms) + "Question: "+ remove_backticked_imbeds(question["Question"]) + "Definition: " + question["D" + str(i + 1)]},
                            {"type": "image_url", "image_url": {
                                "url": img_link
                            }} 
                        ] if img_link != "" else [
                            {"type": "text", "text": domain_c + context_c + REQUEST_GENERATE_TERM.replace("{X}", terms) + "Question: "+ remove_backticked_imbeds(question["Question"]) + "Definition: " + question["D" + str(i + 1)]}
                        ]
                    }
                ]
            )

            print(response.choices[0].message.content)


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

def get_question_sample(bank):
    # get the proportionate amounts of each question type in the bank, while also currating lists for each of the 3 question types
    mc_questions = []
    td_questions = []
    ess_questions = []
    for question in bank:
        match question["Type"]:
            case "MC":
                mc_questions += [question]
            case "TD":
                td_questions += [question]
            case "Ess":
                ess_questions += [question]
    proportions = (len(mc_questions) / len(bank), len(td_questions) / len(bank), len(ess_questions) / len(bank))
    
    # using those proportions, select a type to generate a sample of
    sel_type = ""
    selection = random.random()
    if selection < proportions[0]:
        sel_type = "MC"
    elif selection < proportions[0] + proportions[1]:
        sel_type = "TD"
    else:
        sel_type = "Ess"
    
    # choose the appropriate number of questions to create the sample
    match sel_type:
        case "MC":
            sample = random.sample(mc_questions, 3)
        case "TD":
            sample = random.sample(td_questions, 1)
        case "Ess":
            sample = random.sample(ess_questions, 1)
    
    # return the sample
    return sample

def batch_generate_questions(bank, count, domain, context, api_key, model):
    # store ALL AI generated questions in an accumulated list
    ai_generated_questions = []
    
    # create as many threads as needed to process the count, using constants on max threads and batch size to determine our thread distribution
    threads = []
    results = []
    while count > 0:
        # get a quota for this iteration
        quota = MAX_THREADS * THREAD_SIZE if count >= MAX_THREADS * THREAD_SIZE else count
        num_of_threads = quota // THREAD_SIZE + 1 if quota < MAX_THREADS * THREAD_SIZE else MAX_THREADS
        size_of_last_thread = quota % THREAD_SIZE if quota < MAX_THREADS * THREAD_SIZE else THREAD_SIZE
        for i in range(num_of_threads):
            # get a sample of either 3 multiple choice questions, 1 TD question, or 1 essay question, where the type of question we sample is determined by the proportion of that question type in the bank
            sample = get_question_sample(bank)
            
            threads.append(threading.Thread(target=generate_questions, args=(sample, THREAD_SIZE if i < num_of_threads - 1 else size_of_last_thread, domain, context, api_key, model, results)))
            threads[i].start()
        for i in range(num_of_threads):
            threads[i].join()
        ai_generated_questions += results
        threads.clear()
        results.clear()
        count -= MAX_THREADS * THREAD_SIZE
        
    # once all of the questions are generated, go back and update the q_indicies of every question
    q_count = len(bank)
    print(ai_generated_questions)
    for question in ai_generated_questions:
        q_count += 1
        question["Q"] = str(q_count)
        
    # return the AI generated questions collected
    return ai_generated_questions

def generate_questions(sample, count, domain, context, api_key, model, t_results):    
    # break immediately if we are to generate 0 questions
    if count == 0:
        return []
    
    # create client
    client = OpenAI(api_key=api_key)
    domain_c = "Domain: " + domain + "\n"
    context_c = "Context: " + get_random_context_segment(context, CONTEXT_CUTOFF) + "\n"
    model_c = "gpt-4o-mini" if model == '3.5' else "gpt-4o"
    
    # get a textual representation of the prompt count to emphasize the amount requested
    if count == 1:
        num_of_questions = "ONE"
    elif count == 2:
        num_of_questions = "TWO"
    elif count == 3:
        num_of_questions = "THREE"
    elif count == 4:
        num_of_questions = "FOUR"
    elif count == 5:
        num_of_questions = "FIVE"
        
    # format the questions of the sample cleanly for the AI to use as an example
    questions = ""
    for question in sample:
        for key, value in question.items():
            # see if we are writing the question
            if key == "Question":
                questions += "Q~ " + remove_backticked_imbeds(value) + "\n"
            elif "C" in key:
                questions += "C~ " + value + "\n"
            elif "A" in key:
                questions += "I~ " + value + "\n"
            elif "T" in key and key != "Type":
                questions += f"{key}~ " + value + "\n"
            elif "D" in key:
                questions += f"{key}~ " + value + "\n"
            elif "Guidelines" in key:
                questions += 'G~ "' + value + '"\n'
            elif "Format" in key:
                questions += "F~ " + value + "\n"
            elif "Language" in key:
                questions += "L~ " + value + "\n"
            elif key == "Explaination":
                questions += "E~ " + value + "\n"
        # append seperator
        questions += "\n"
        
    # prompt the GPT for the question
    response = client.chat.completions.create (
        model = model_c,
        presence_penalty= 2,
        messages = [
            {"role": "system", "content": SYSTEM_INTRO + REQUEST_EXAMPLE_QUESTIONS.replace('{X}', str(len(sample))).replace('{Y}', num_of_questions) + SYSTEM_CONCLUSION},
            {
                "role":"user",
                "content": [
                    {"type": "text", "text": domain_c + context_c + questions + REQUEST_QUESTIONS.replace('{X}', num_of_questions)}
                ]
            }
        ]
    )
    
    # parse the output produced by the GPT by splitting by the line
    result = response.choices[0].message.content.split('\n')
    print(result)
    key_parse = [tuple(line.split('~')) for line in result]
    key_parse = [(key.strip(), item.strip()) for key, item in key_parse]
    print(key_parse)
    
    # if the sample was TD, we need to count how many terms/definitions we got
    num_of_terms = 0
    for key, item in key_parse:
        if key.startswith("T"):
            num_of_terms = max(num_of_terms, int(key[1:]))
    
    # use lists to keep track of items that we have multiplies of
    key_keys = {}
    corrects = []
    incorrects = []
    terms = [["",""] for _ in range(num_of_terms)]
    print(terms)
    for key, item in key_parse:
        # check for key keys
        if key.startswith("Q"):
            key_keys['Question'] = item
        elif key.startswith("G"):
            key_keys['Guidelines'] = item
        elif key.startswith("F"):
            key_keys['Format'] = item
        elif key.startswith("L"):
            key_keys['Language'] = item
        elif key.startswith("E"):
            key_keys['Explaination'] = item
        
        # add iterables to their lists
        if key.startswith("C"):
            corrects += [item]
        elif key.startswith("I"):
            incorrects += [item]
        elif key.startswith("T"):
            terms[int(key[1:]) - 1][0] = item
        elif key.startswith("D"):
            terms[int(key[1:]) - 1][1] = item
            
    # convert all term lists to tuples
    for term in terms:
        term = tuple(term)
    
    # using the parsed information, attempt to construct the correct question object based on the sampling type
    match sample[0]['Type']:
        case "MC":
            t_results += [construct_question_object("Multiple Choice", key_keys["Question"], "-1", corrects, incorrects, forced="0", explaination=key_keys["Explaination"])]
        case "TD":
            t_results += [construct_question_object("Term-Definition", key_keys["Question"], "-1", forced="0", terms=terms, explaination=key_keys["Explaination"])]
        case "Ess":
            t_results += [construct_question_object("Essay", key_keys["Question"], "-1", forced="0", guidelines=key_keys["Guidelines"], format=key_keys["Format"], language=key_keys["Language"], explaination=key_keys["Explaination"])]
            
    print(t_results)
    return

def get_random_numaric_str(unique_arr, character_set, stri, unique):
    # copy the passed string to modify
    num_str = stri
    
    # iterate over the characters of the provided numaric string
    for i in range(len(num_str)):
        # if the character is not in the character set, replace it with a character from the character set
        if not num_str[i] in character_set:
            num_str = num_str[:i] + random.choice(character_set[:-1]) + (num_str[i+1:] if i < len(num_str) - 1 else "")
    
    # perform 100 attempts at generating a unique bit string if specified
    attempts = 0
    while unique and attempts < 100 and num_str in unique_arr:
        # reset number string
        num_str = stri
        
        # iterate over the characters of the provided numaric string
        for i in range(len(num_str)):
            # if the character is not in the character set, replace it with a character from the character set
            if not num_str[i] in character_set:
                num_str = num_str[:i] + random.choice(character_set) + (num_str[i+1:] if i < len(num_str) - 1 else "")
                
    # add the bit string to the unique list
    unique_arr += [num_str]
    
    # return the result
    return num_str
    
def get_random_number(unique_arr, base, min, max, n, unique):
    # validate bounds check
    if n < 1:
        n = 1
        
    # iterate to make the list of numbers
    result = ""
    for i in range(n):
        # attempt to generate the random number
        rand_num = random.randint(min, max)
        
        # perform 100 attempts at generating a unique number if specified
        attempts = 0
        while unique and attempts < 100 and rand_num in unique_arr:
            # attempt to generate the random number
            rand_num = random.randint(max, min)
            attempts += 1
            
        # add the number to the unique list
        num = int_to_base(rand_num, base)
        unique_arr += [num]
        
        # add to result w/ a comma if necessary
        result += num
        if i < n - 1:
            result += ", "
            
    # return the result
    return result

def int_to_base(number, base):
    # correct base
    base = max(min(base, 64), 0)
        
    # define character set
    if base < 36:
        digits = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    else:
        digits = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
    
    # default 0 case
    if number == 0:
        return '0'
    
    result = ''
    negative = False
    
    # remeber negavity
    if number < 0:
        number = -number
        negative = True
    
    # successively divide by the base and encode the remainder as its respective digit according to the digit character set.
    while number > 0:
        number, remainder = divmod(number, base)
        result = digits[remainder] + result
    
    # add the negative back if needed
    if negative:
        result = '-' + result
    
    # return the result
    return result

def seed_permutations_in_question(question_text, domain, context, api_key, model):
    # First retrieve an image embed if it exists
    img_link = get_image_embed_links_if_any(question_text)
    
    # Split the question content into chunks to search for the first img embed
    embeds = question_text.split('```')
    
    # For numbers to track uniqueness, we use a list
    unique_vals = []
    
    # Keep references for 2 seperate lists:
    segments = [""] # Segments of the completed final string
    segment_c = 0
    blank_defaults = [] # The original values of blanks, as well as the "type" of permutateable part they are
    blanks = [] # The blanks to slowly use to guide GPT to constructing a permutated question
    
    for i, chunk in enumerate(embeds):
        if i % 2 != 0:
            # determine what imbed we are using
            header = chunk.split(':')[0]
            if header == "prt":
                # this is a permutatable text part, get the original text and add it to the cut segment
                blank_defaults.append((chunk[4:], "reg"))
                blanks.append("_" * len(chunk[4:]))
                segment_c += 1 # add a new empty segment to catch the static text of the next segement after this blank
                segments += [""] 
            elif header == "mathprt":
                # this is a MATH permutatable part, signify this in the tuple, otherwise its the same as a prt segment
                blank_defaults.append((chunk[8:], "math"))
                blanks.append("_" * len(chunk[8:]))
                segment_c += 1 # add a new empty segment to catch the static text of the next segement after this blank
                segments += [""]
            elif header == "rng":
                # this is a random integer permutable part, which is foramtted as: ```rng:base:min:max:n:unique```
                # get those args and pass them into the randomization function
                try:
                    default_args = ["per_name", 10, 1, 10, 1, False]
                    args = chunk.split(':')
                    argc = len(args)
                    for i in range(1, 6):
                        if i < argc:
                            args[i] = int(args[i]) if i != 5 else ("t" in args[i].strip().lower())
                            continue
                        args += [default_args[i]]
                    args.pop(0)
                    print(args)
                    # automatically fill the blank with the random number
                    segments[segment_c] += get_random_number(unique_vals, *args)
                except Exception as e:
                    print("Malformated Embed " + str(e))
                    segments[segment_c] += str(0)
            elif header == "rnstr":
                # this is a binary permutable part, which is foramtted as: ```rnstr:base:str:unique```
                # get those args and pass them into the randomization function
                try:
                    default_args = ["per_name", 10, "-", False]
                    args = chunk.split(':')
                    argc = len(args)
                    for i in range(1, 4):
                        if i < argc:
                            if i == 1:
                                args[i] = int(args[i])
                            elif i == 3:
                                args[i] = ("t" in args[i].strip().lower())
                            continue
                        args += [default_args[i]]
                    args.pop(0)
                    
                    base = args.pop(0)
                    # correct base
                    base = min(max(base, 0), 64)
                        
                    # define character set
                    if base < 36:
                        digits = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                    else:
                        digits = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"

                    # automatically fill the blank with the random number
                    segments[segment_c] += get_random_numaric_str(unique_vals, digits[0:base] + "_", *args)
                except Exception as e:
                    print("Malformated Embed " + str(e))
                    segments[segment_c] += str(0)
            else:
                # readd embed markings if not an image embed
                if not chunk.startswith("img:"):
                    segments[segment_c] += "```" + chunk + "```"
        else:
            # log segment as is
            segments[segment_c] += chunk
                    
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
    
        # prompt the GPT to fill in the blank
        response = client.chat.completions.create (
            model = model_c,
            presence_penalty= 2,
            messages = [
                {"role": "system", "content": SYSTEM_INTRO + (REQUEST_EXAMPLE_FILL_IN_BLANKS if cur_blank[1] == "reg" else REQUEST_EXAMPLE_FILL_IN_MATH) + SYSTEM_CONCLUSION + (IMG_SPECIFICATION if img_link != "" else "")},
                {
                    "role":"user",
                    "content": [
                        {"type": "text", "text": domain_c + context_c + REQUEST_FILL_IN_BLANKS + question_c},
                        {"type": "image_url", "image_url": {
                            "url": img_link
                        }} 
                    ] if img_link != "" else [
                        {"type": "text", "text": domain_c + context_c + REQUEST_FILL_IN_BLANKS + question_c}
                    ]
                }
            ]
        )
        
        try:
            # pick one of the 5 options at basically random
            options = response.choices[0].message.content.split('\n')
            print(options)
            best_option = random.choice(options)

            if cur_blank[1] == "reg":
                segments.insert(0, comb_segments[0] + best_option.strip() + comb_segments[1])
            else:
                segments.insert(0, comb_segments[0] + "```math:" + best_option.strip() + "```" + comb_segments[1])
        except Exception as e:
            print("Failed call to GPT! " + str(e))
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
        question['Explaination'] = response.choices[0].message.content[2:].strip().replace('\\\\', '\\')
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

def import_from_quizzy_file():
    # get the path to the file we want to open
    print("Requesting Quizzy file location...")
    bank_path = filedialog.askopenfilename(defaultextension='.qizy', filetypes=[("Quizzy Files", "*.qizy")])
    
    # check if the path is valid
    if bank_path:
        try:
            # open the file for parsing
            with open(bank_path, 'r', encoding='utf-8') as import_file:
                json_data = import_file.read()
                
            # convert from JSON to dictionary
            py_obj = json.loads(json_data)
            extracted_values = py_obj
            
            # check if all contents are there
            domain = extracted_values['Domain']
            print("Read domain successfully!")
            context = extracted_values['Context']
            print("Read context successfully!")
            data = extracted_values['Data']
            print("Read data successfully!")
            print("All contents found SUCCESSFULLY!")
            
            # iterate through the question objects and modify/validate them to be correct
            valid = all(validate_question_object(obj) for obj in data)
            if not valid:
                print("Failed to read Quizzy file. Is it formatted correctly?")
            else:
                # return the domain, context, and data segment as a tuple
                print("Data segment VALIDATED!")
                print("Successfully read Quizzy file!")
                return (domain, context, data)
        except Exception as e:
            print("Failed to read Quizzy file. Is it formatted correctly?")
    else:
        print("Failed to find Quizzy file. Is the path correct?")
        
    return ("No domain provided", "No context provided", [])

def export_to_quizzy_file(domain, context, data):
    # get the path to the file we want to save
    print("Requesting location to store Quizzy file at...")
    save_path = filedialog.asksaveasfile(initialfile=f'{domain}.qizy', mode='w', defaultextension='.qizy', filetypes=[("Quizzy Files", "*.qizy"), ("All Files", "*.*")]).name # File dialog to get a file path to save at

    # fail if the file path is invalid
    if not save_path:
        print("Failed to find path. Was it written correctly?")
        return False
    
    # create a save data object
    save = {"Domain":domain,
            "Context":context,
            "Data":data}
    
    # export to JSON file
    json_data = json.dumps(save, indent=4)
    with open(save_path, 'w', encoding='utf-8') as export:
        # write to destination
        export.write(json_data)
        
    print("Successfully saved Quizzy file")
    return True

if __name__ == "__main__":
    driver_loop = True
    
    domain = input("Enter the domain segment: ")
    print("Requesting file that contains context...")
    try:
        context_file = filedialog.askopenfilename(defaultextension='.txt', filetypes=[("Text", "*.txt")])
        context = open(context_file, "r").read()
        print("Successfully read from context file")
    except Exception as e:
        context = "No context provided"
        print("Failed to read context file")
    model = "3.5"
    online = True
    
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
    question_index = 1
    question_bank = []
    while driver_loop:
        match get_driver_function():
            case 1:
                print("API key is valid!" if test_api_key(api_key) else "API key is INVALID!")
            case 2:
                print(question_bank)
            case 3:
                results = import_from_quizzy_file()
                if results[2] is not []:
                    domain = results[0]
                    context = results[1]
                    question_bank = results[2]
                    question_index = len(question_bank) + 1
            case 4:
                export_to_quizzy_file(domain, context, question_bank)
            case 5:
                question = get_question_from_user_input(question_index)
                match question['Type']:
                    case 'MC':
                        fill_multiple_choice_options(question, domain, context, api_key, model)
                    case 'TD':
                        fill_matching_options(question, False, domain, context, api_key, model)
                    case 'Ess':
                        print("Not implemented")

                generate_explaination_for_question(question, domain, context, api_key, model)

                print(question)

                question_bank += [question]

                question_index += 1
                
            case 6:
                question = get_question_from_user_input(0)
                n = int(input("How many questions do you wish to generate? "))
                threads = []
                results = []
                while n > 0:
                    for i in range(MAX_THREADS if n // MAX_THREADS > 0 else n):
                        threads.append(threading.Thread(target=generate_permutation_from_question, args=(question, domain, context, api_key, model, results)))
                        threads[i].start()
                    for i in range(MAX_THREADS if n // MAX_THREADS > 0 else n):
                        threads[i].join()
                    for i in range(MAX_THREADS if n // MAX_THREADS > 0 else n):
                        print(results[i])
                    threads.clear()
                    results.clear()
                    n -= MAX_THREADS
            case 7:
                n = int(input("How many questions do you wish to generate? "))
                question_bank += batch_generate_questions(question_bank, n, domain, context, api_key, model)
                question_index = len(question_bank) + 1
            case 8:
                driver_loop = False