import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
from options import *
from openai import OpenAI
import random
from PIL import Image
from color_lerp import *
import Levenshtein as lev
import requests
from io import BytesIO
import matplotlib.pyplot as plt

def create_embed_frame(parent, source, wrap_limit, image_limit):
    # get imbeds from source
    imbeds = source.split('```')
    
    # create a frame to return
    question = ctk.CTkFrame(parent, fg_color='transparent')
    
    for i, chunk in enumerate(imbeds):
        if i % 2 == 0: 
            formatted_question = wrap_text(chunk, wrap_limit)
            # this is a plaintext segement, write it out
            embed = ctk.CTkLabel(question, text=formatted_question, fg_color='transparent', justify='left', font=(FONT, NORMAL_FONT_SIZE)).pack(padx=5, pady=1, anchor='w')
        else:
            # determine what imbed we are using
            header = chunk.split(':')[0]
            if header == "img":
                # we are imbedding an image, remove header from string
                link = chunk[4:]
                
                # fetch the image using a request
                response = requests.get(link)
                
                # check if successful
                if response.status_code == 200:
                    # convert the response to an image and render it as an imbed
                    image = Image.open(BytesIO(response.content))
                    width, height = image.size
                    width = width if width < image_limit else image_limit
                    height = height if height < image_limit else image_limit
                    img_ref = ctk.CTkImage(image, size=(width, height))
                    embed = ctk.CTkLabel(question, text="", fg_color='transparent', image=img_ref).pack(padx=5, pady=1, anchor='w', expand=True, fill='both')

                else:
                    # render placeholder instead
                    embed = ctk.CTkLabel(question, text="ERROR RENDERING ELEMENT: Failed to grab image!"+ str(response) +"\n@"+link[:50]+"...", fg_color='transparent', text_color=PRIMARY, justify='left', font=(FONT, NORMAL_FONT_SIZE, 'bold')).pack(padx=5, pady=3, anchor='w')
            elif header == "math":
                # we are imbedding latex math, remove header from string
                latex = "$" + chunk[5:] + "$"
                
                try:
                    # create an image of the latex expression
                    fig = plt.figure(figsize=(6, 1), frameon=False)
                    fig.text(0.5, 0.5, latex, size=12, ha='center', va='center')
                    plt.axis('off')
                    plt.savefig("output.png", bbox_inches='tight', pad_inches=0)
                    plt.close('all')
                    
                    # fix the image to only contain the content of the latex expression
                    latex_image = Image.open("output.png")
                    bbox = latex_image.getbbox()
                    image = latex_image.crop(bbox)
                    
                    # convert the response to an image and render it as an imbed
                    width, height = image.size
                    img_ref = ctk.CTkImage(image, size=(width, height))
                    embed = ctk.CTkLabel(question, text="", fg_color='transparent', image=img_ref).pack(padx=5, pady=1, anchor='w')
                    
                    # delete tmp file
                    os.remove("output.png")
                except Exception as e:
                    # catch bad formatting and use placeholder instead
                    embed = ctk.CTkLabel(question, text="ERROR RENDERING ELEMENT: Bad LaTeX!\n" + str(e), fg_color='transparent', text_color=PRIMARY, justify='left', font=(FONT, NORMAL_FONT_SIZE, 'bold')).pack(padx=5, pady=1, anchor='w')
            elif header == "code":
                # we are imbedding a code segment, remove header from string
                code_seg = chunk[5:]
                
                # create a frame to place the code segment in
                c_frame = ctk.CTkFrame(question, fg_color=DARK)
                
                # write the code into the segment
                embed = ctk.CTkLabel(c_frame, text=code_seg, fg_color='transparent', text_color=SELECT_FG, justify='left', font=(CODE_FONT, NORMAL_FONT_SIZE)).pack(padx=4, pady=4, expand=True, fill='both')
                
                # imbed
                c_frame.pack(padx=5, pady=1, anchor='w')
            else:
                # invalid imbed header
                embed = ctk.CTkLabel(question, text="ERROR RENDERING ELEMENT: Not a valid imbed header!\n"+"```"+chunk+"```", fg_color='transparent', text_color=PRIMARY, justify='left', font=(FONT, NORMAL_FONT_SIZE, 'bold')).pack(padx=5, pady=1, anchor='w')
    
    # return this frame
    return question

def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False

def numaric_comparision_grading(answers, correct_answers):
    # get a list of similarities and copy the collections
    similarities = []
    ans = answers.copy()
    cor_ans = correct_answers.copy()
    
    # iterate through the numbers in the ans list
    for answer in ans:
        # check if this answer is numaric
        if not is_number(answer):
            similarities.append(0.0)
            
            continue
        
        most_similar = ""
        best_similarity = 0.0
        # iterate through the cor_ans list
        for correct in cor_ans:
            # get the percent distance from this answer
            distance = abs(float(answer) - float(correct)) / float(correct)
            # get a ratio of value with a 5% confidence
            similarity = 1 - min(distance / 0.05, 1)
            
            # compare with the score already logged for this answer
            if similarity > best_similarity:
                # save as best, remember with what string
                best_similarity = similarity
                most_similar = correct
                
        # check if a record was found to be similar
        if best_similarity == 0.0:
            # append a score of 0
            similarities.append(0.0)
            
            # continue
            continue
                
        # record this similarity and remove the most similar string from answer collection
        similarities.append(best_similarity)
        cor_ans.remove(most_similar)
        
    # return results
    return similarities

def answer_comparision_grading(answers, correct_answers):
    # get a list of similarities and copy the lowercase conversion collections
    similarities = []
    ans = [ans.lower() for ans in answers]
    cor_ans = [ans.lower() for ans in correct_answers]
    
    # iterate through the strings in the ans list
    for answer in ans:
        most_similar = ""
        best_similarity = 0.0
        best_diff = 0.0
        
        # iterate through the cor_ans list
        for correct in cor_ans:
            # get the Levenshtein similarity score between these 2 strinsg
            distance = lev.distance(answer, correct)
            max_length = max(len(answer), len(correct))
            difference = (distance / max_length)
            # get a ratio of value with 25% confidence
            similarity = 1 - min(difference/.25, 1)
            
            # compare with the score already logged for this answer
            if similarity > best_similarity:
                # save as best, remember with what string
                best_similarity = similarity
                most_similar = correct
                best_diff = difference
                
        # check if a record was found to be similar
        if best_similarity == 0.0:
            # append a score of 0
            similarities.append(0.0)
            
            # continue
            continue
                
        # record this similarity and remove the most similar string from answer collection and this answer
        similarities.append(best_similarity)
        cor_ans.remove(most_similar)
        
    # return results
    return similarities

def wrap_text(text, max_width):
    words = text.split(' ')
    lines = []
    current_line = words[0]

    for word in words[1:]:
        if len(current_line + ' ' + word) <= max_width:
            current_line += ' ' + word
        else:
            lines.append(current_line)
            current_line = word
    lines.append(current_line)
    return '\n'.join(lines)

def format_seconds(seconds):
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours > 0:
        return "{:2}:{:02}:{:02}".format(hours, minutes, seconds)
    else:
        return "{:2}:{:02}".format(minutes, seconds)

class Quiz(ctk.CTkFrame):
    def __init__(self, parent, data, question_bank, question_count, ai_prop, frq_prop, per_page, time_limit, get_builder, modified, settings):
        super().__init__(parent, fg_color='transparent')
        
        # data
        self.domain = data[0]
        self.context = data[1]
        self.question_bank = question_bank
        self.question_count = question_count
        self.ai_prop = ai_prop
        self.frq_prop = frq_prop / 100.0
        self.get_builder = get_builder
        self.per_page = per_page
        self.cur_page = 0
        self.graded = False
        self.was_modified = modified
        self.timer = time_limit * 60
        self.settings = settings
        
        # get the number of questions to generate from chatGPT
        self.ai_q_count = round(self.question_count * self.ai_prop)
        
        # get the AI generated questions, make a copy for one pool without questions
        self.bank = self.question_bank.copy()
        ai_questions = self.generate_questions()
        self.question_bank += ai_questions
        
        # if we have a timer, create a frame and label for said timer
        self.timer_frame = None
        if self.timer > 0:
            self.timer_frame = ctk.CTkFrame(self, fg_color=LIGHT)
            self.timer_label = ctk.CTkLabel(self.timer_frame, text="Time Left:", fg_color='transparent', font=(FONT, TITLE_FONT_SIZE), anchor='w')
            self.timer_label.pack(side='left',padx=4, pady=10)
            self.timer_widget = ctk.CTkLabel(self.timer_frame, text=format_seconds(self.timer), fg_color='transparent', font=(FONT, TITLE_FONT_SIZE, 'bold'), anchor='w')
            self.timer_widget.pack(side='left',padx=4, pady=10)
            self.timer_frame.pack(fill='x')
        
        # create a frame to store buttons to go to each question from anywhere in the quiz, of which also store the state on which each question is answered or not
        self.question_nav = ctk.CTkFrame(self, fg_color=LIGHT)
        
        # create n questions
        self.questions = []
        self.question_frame = ctk.CTkScrollableFrame(self, fg_color='transparent')
        for i in range(self.question_count):
            # first, decide wheither or not to pick an ai question using the ai prop
            # this choice is random until we need to meet the budget for ai questions requested
            roll_em = random.random()
            if (random.random() <= self.ai_prop and ai_questions) or self.question_count - len(self.questions) == len(ai_questions):
                # pick an ai question and remove it from the ai bank
                cur_question = random.choice(ai_questions)
                ai_questions.remove(cur_question)
                roll_em = 2
            else:
                # pick a random question and remove it from the question bank
                cur_question = random.choice(self.bank)
                self.bank.remove(cur_question)
            self.questions.append(QuizQuestion(self.question_frame, self, cur_question, i, roll_em == 2, roll_em <= self.frq_prop))
            
        # create and pack a button for each question in the entire quiz, even if they may not be on the current page
        self.question_buttons = []
        self.question_nav_rows = []
        for i in range(len(self.questions)):
            # check if we are on a new row
            if (i < 94 and (i) % 31 == 0) or (i == 119) or (i > 119 and (i - 119) % 25 == 0):
                # pack new row and use that
                self.question_nav_rows.append(ctk.CTkFrame(self.question_nav, fg_color=LIGHT))
                self.question_nav_rows[-1].pack(fill='x', expand=True)
                
            # pack button
            self.question_buttons.append(ctk.CTkButton(self.question_nav_rows[-1], text=i + 1, width=28, fg_color=BG, text_color=DARK, font=(FONT, NORMAL_FONT_SIZE), command=lambda x=i:self.get_question(x)))
            self.question_buttons[-1].pack(side='left', anchor='n', padx=2, pady=2)
        # pack the nav
        self.question_nav.pack(fill='x')
        
        # pack the first p_count questions into the question frame
        for i in range(per_page if per_page < len(self.questions) else len(self.questions)):
            self.questions[i].pack(expand=True, fill='x', padx=10, pady=10, ipady=5)
        self.question_frame.pack(expand=True, fill='both')
        
        # pack the quiz naviagation frame
        self.quiz_nav = ctk.CTkFrame(self,fg_color='transparent')
        self.prev_page = ctk.CTkButton(self.quiz_nav, fg_color=SECONDARY, text="Previous Page", command=lambda:self.get_rel_page(-1), font=(FONT, NORMAL_FONT_SIZE))
        self.next_page = ctk.CTkButton(self.quiz_nav, fg_color=SECONDARY, text="Next Page", command=lambda:self.get_rel_page(1), font=(FONT, NORMAL_FONT_SIZE))
        self.grade_button = ctk.CTkButton(self.quiz_nav, fg_color=SUCCESS, text="Submit Quiz", command=self.grade_quiz, font=(FONT, NORMAL_FONT_SIZE))
        self.next_page.pack(padx=10, pady=5)
        self.quiz_nav.pack()
        
        # assemble first page properly
        self.get_page(0)
        
        # start the timer if needed
        if self.timer > 0:
            self.update_timer()
        
        # pack self
        self.pack(expand=True, fill='both')
        
    def update_timer(self):
        # check if there is time left
        if self.timer > 0:
            # decrement timer
            self.timer -= 1
            
            # update timer label
            self.timer_widget.configure(text=format_seconds(self.timer))
            
            # recolor label if below a certain threshold
            if(self.timer < 60):
                # color with red
                self.timer_label.configure(text_color=PRIMARY)
                self.timer_widget.configure(text_color=PRIMARY)
            elif(self.timer < 300):
                # color with orange/yellow
                self.timer_label.configure(text_color=WARNING)
                self.timer_widget.configure(text_color=WARNING)
            
            # call timer again
            self.after(1000, self.update_timer)
        # time is up
        else:
            # force submit quiz
            if not self.graded:
                self.grade_quiz(True)
            
        
    def get_question(self, question):
        # first, check if this question is on the currently rendered page
        if not question in range(self.cur_page * self.per_page, (self.cur_page + 1) * self.per_page):
            # if not in range, fetch the page that this question would be in range of
            self.get_page((question) // (self.per_page), False, question)
            
        # scroll to where that question is with respect to the scrollable frame
        self.question_frame._parent_canvas.yview_moveto(self.questions[question].winfo_y()/self.question_frame.winfo_height())
        
    def get_rel_page(self, rel):
        # call the get page function using a relative value to the current page
        self.get_page(self.cur_page + rel)
     
    def get_page(self, page, scroll = True, question = 0):
        # check if this is a valid page
        if page > (self.question_count - 1) // self.per_page:
            return
        
        # unpack ALL of the questions on the current page
        for i in range(self.cur_page * self.per_page, (self.cur_page + 1) * self.per_page):
            if i < len(self.questions):
                self.questions[i].pack_forget()
        
        # update current page
        self.cur_page = page
        
        # pack ALL of the questions on the passed page (so long as we dont pass the bounds of the questions array)
        for i in range(self.cur_page * self.per_page, (self.cur_page + 1) * self.per_page):
            if i < len(self.questions):
                self.questions[i].pack(expand=True, fill='x', padx=10, pady=10, ipady=5)
                
        # scroll to the top of this page
        if not scroll:
            self.after(10, lambda:self.question_frame._parent_canvas.yview_moveto(self.questions[question].winfo_y()/self.question_frame.winfo_height()))
        else:
            self.question_frame._parent_canvas.yview_moveto(0) 
                
        # update quiz nav
        self.prev_page.pack_forget()
        self.next_page.pack_forget()
        self.grade_button.pack_forget()
        # pack previous page button if not on page 0
        if self.cur_page != 0:
            self.prev_page.pack(side='left', padx=10, pady=5, anchor='center')
        # pack next page button if not on the last page
        if self.cur_page != (self.question_count - 1) // self.per_page:
            self.next_page.pack(side='left', padx=10, pady=5, anchor='center')
        # otherwise pack the submit quiz button (if the quiz is not graded yet!)
        elif not self.graded:
            self.grade_button.pack(side='left', padx=10, pady=5, anchor='center')
        
    def generate_questions(self):
        # create a list to store the ai generated questions
        ai_question_list = []
        
        # break function immediately if 0 ai questions are to be generated
        if self.ai_q_count == 0:
            return ai_question_list
        
        # get a process count
        processed = 0
        
        # configure client
        client = OpenAI(api_key=self.settings['API Key'])
        domain = "Domain: " + self.domain + "\n"
        model = "gpt-4o-mini" if self.settings['Model'] == '3.5' else "gpt-4o"
        warn_missing_explainations = False
        
        # we define the context by selecting a random span of context cut words from said context
        context_words = self.context.split(" ")
        start_point = random.choice(range(0, max(len(context_words) - int(self.settings['ContextCut']), 1)))
        context = "Context: " + " ".join(context_words[start_point:min(start_point+int(self.settings['ContextCut']), len(context_words))]) + "\n"
        
        # iterate over the number of questions to generate (x{batch})
        for __ in range ((self.ai_q_count - 1) // self.settings['Batch'] + 1):
            # get the number of questions to prompt for
            prompt_count = min(self.ai_q_count - processed, self.settings['Batch'])
            
            # get a textual representation of the prompt count to emphasize the amount requested
            if prompt_count == 1:
                num_of_questions = "ONE"
            elif prompt_count == 2:
                num_of_questions = "TWO"
            elif prompt_count == 3:
                num_of_questions = "THREE"
            elif prompt_count == 4:
                num_of_questions = "FOUR"
            elif prompt_count == 5:
                num_of_questions = "FIVE"
            
            # pull 3 sample questions to prompt from the slide deck
            sample = random.sample(self.bank, 3)
            questions = ""
            for question in sample:
                for key, value in question.items():
                    # see if we are writing the question
                    if key == "Question":
                        questions += "Q~ " + value + "\n"
                    elif "C" in key:
                        questions += "C~ " + value + "\n"
                    elif "A" in key:
                        questions += "I~ " + value + "\n"
                    elif key == "Explaination":
                        questions += "E~ " + value + "\n"
                # append seperator
                questions += "\n"
            
            # set the environment up
            system1 = """You are an assistant knowledgeable in many academic subjects. In particular, the user is a student who will specify what domain they request that you fetch knowledge from, while also providing a small paragraph of context that helps you generate helpful responses for the user.

                        In particular, your responses are tailored to generating practice test questions, whether that be filling in missing parts of user-created questions such as picking correct answers, generating incorrect answers, or writing an explanation as to why the correct answer is the correct answer. You will also be providing full-on new practice questions for the user to practice with based on a subset of questions picked and the ascribed domain and context be provided with every input.

                        The input you receive will also be minimal to help with processing and costs associated. You will ALWAYS be given a domain, denoted with the prefix "Domain:" for which the question comes from. In addition, you will ALWAYS be given a subset of "Context:" for which you should prioritize when synthesizing your answer. Lastly, you will receive one of the following:
                        - The following 3 questions, which are formatted exactly how your output should be formatted (You will provide """+ num_of_questions +""" NEW questions in said format, DO NOT FORGET ANY OF THESE)\n"""
            system2= """For your explainations, make sure it is INSIGHTFUL and HELPFUL for the student, DO NOT USE ELEMENTS OF THE QUESTION OR ANSWERS WORD FOR WORD IN YOUR RESPONSE.
                        Since your output will be fed directly to a program to be parsed, you MUST be STRICT with what you output, and be as BRIEF as possible. for ALL outputs, your responses MUST ADHERE TO THE ABOVE FORMAT NO MATTER WHAT
                        
                        Please keep in mind you are free to use any characters in your response as the delimiters will help the program figure out what field means what.\n"""
            
            # get the required context for the prompt
            request = "Please provide the requested " + num_of_questions + " questions in the same format as the provided questions were for your reference"
            
            # prompt for answer choices
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system1 + questions + system2},
                    {"role": "user", "content": domain + context + request}
                ]
            )
            
            # process response
            # use dictionaries to represent the newly constructed questions
            cur_question = {}
            cur_key = ""
            
            # split the input by the line
            lines = response.choices[0].message.content.split('\n')
            
            # start parsing
            # reset answer counts
            cor_ans = 0
            incor_ans = 0
            try:
                i = int(self.question_bank[-1]['Q']) + processed
                for line in lines:
                    # check if the line starts with a question, indicating we are moving to the next question's contents
                    if line.startswith("Q~"):
                        # if we have started on a question, add it to our question collection
                        if cur_question:
                            ai_question_list.append(cur_question)
                            
                        # inc. i, set key
                        i += 1
                        cur_key = "Question"
                        
                        # reset answer counts
                        cor_ans = 0
                        incor_ans = 0
                            
                        # start a new question, indexed with i
                        cur_question = {'Q': str(i)}
                        
                        # add a keys to flag that this is an AI generated question
                        cur_question["AI Generated"] = 'True'
                        cur_question["Forced"] = '1'
                        
                        # write this question to its key, with the prefix removed
                        cur_question[cur_key] = line[2:].strip()
                    elif line.startswith('C~'):
                        # we have hit a correct answer
                        # create and update key
                        cor_ans += 1
                        cur_key = "C" + str(cor_ans)
                        
                        cur_question[cur_key] = line[2:].strip()
                    elif line.startswith('I~'):
                        # we have hit a incorrect answer
                        # create and update key
                        incor_ans += 1
                        cur_key = "A" + str(incor_ans)
                        
                        cur_question[cur_key] = line[2:].strip()
                    elif line.startswith('E~'):
                        # we have hit the explaination
                        # create and update key
                        cur_key = "Explaination"
                        
                        cur_question[cur_key] = line[2:].strip()
                    elif len(line.strip()) < 1:
                        # skip empty lines
                        continue
                    else:
                        # check if we even have a key yet
                        if cur_key != '':
                            # this line is a continuation from the previous line due to new line, report this
                            cur_question[cur_key] += "\n" + line
                        # otherwise skip
                        else:
                            continue
                            
                # add the last question to the list
                if cur_question:
                    ai_question_list.append(cur_question)      
            except Exception as e:
                # report error
                messagebox.showerror("Woops!", "There was an error when generating new questions, some new questions may have been generated, but not enough to meet the quota amount. Sorry about that :p")
                
                return []
                
            # this check is kinda unstable so uhhhhh
            try:
                # before continuing, ensure that this batch was correctly parsed
                for i in range(processed, processed + prompt_count):
                    # check for the following keys, error if ANY are missing
                    if not all(item in ai_question_list[i].keys() for item in ['Question', 'C1', 'A1', 'Explaination']):
                        # before all is naught, if the explaination is missing just simply use a placeholder, its not required!
                        if all(item in ai_question_list[i].keys() for item in ['Question', 'C1', 'A1']):
                            ai_question_list[i]["Explaination"] = "No explaination was generated :("
                            
                            # flag a report for clarity when done
                            warn_missing_explainations = True
                            
                            # continue
                            continue
                        
                        # report error
                        messagebox.showerror("Life happens!", "There was an error parsing this batch of questions, all passing batches will be included in this quiz. Sorry about that :p")
                        
                        # return all valids up to this point
                        return ai_question_list[:processed-1]
            except Exception as e:
                # report error
                messagebox.showerror("Life happens!", "There was an error parsing this batch of questions, all passing batches will be included in this quiz. Sorry about that :p")
                
            # update process count
            processed += prompt_count
            
        if(warn_missing_explainations):
            messagebox.showwarning("Heads up!", "A batch of questions was passed, but their explainations will have to be generated after your quiz!")
            
        return ai_question_list
        
    def grade_quiz(self, forced = False):
        # ask if the user wants to submit their quiz for sure
        if not forced and not messagebox.askyesno("Last Call!", "Are you sure you want to submit your quiz for a final grade?"):
            return
        
        # flag the state of being graded
        self.graded = True
        
        # remove timer frame (if it exists)
        if self.timer_frame:
            self.timer_frame.destroy()
            self.timer = 0
        
        # goto the first page
        self.get_page(0)
        
        # iterate through the quiz questions and have them grade themselves, then get their point value
        total = 0
        out_of_total = 0
        for question in self.questions:
            question.grade()
            total += question.score
            out_of_total += question.point_total
        percentage = round(total / out_of_total, 4)
            
        # get the letter grade
        if percentage >= .97:
            letter_grade = 'A+'
        elif percentage >= .93:
            letter_grade = 'A'
        elif percentage >= .9:
            letter_grade = 'A-'
        elif percentage >= .87:
            letter_grade = 'B+'
        elif percentage >= .83:
            letter_grade = 'B'
        elif percentage >= .8:
            letter_grade = 'B-'
        elif percentage >= .77:
            letter_grade = 'C+'
        elif percentage >= .73:
            letter_grade = 'C'
        elif percentage >= .7:
            letter_grade = 'C-'
        elif percentage >= .67:
            letter_grade = 'D+'
        elif percentage >= .63:
            letter_grade = 'D'
        elif percentage >= .6:
            letter_grade = 'D-'
        elif percentage >= .57:
            letter_grade = 'F+'
        elif percentage >= .53:
            letter_grade = 'F'
        else:
            letter_grade = 'F-'
            
        # draw the frame holding the total score percentage
        grade_frame = ctk.CTkFrame(self, fg_color=LIGHT,corner_radius=0)
        header_frame = ctk.CTkFrame(grade_frame, fg_color='transparent')
        grade_header = ctk.CTkLabel(header_frame, text="Your Score: ", fg_color='transparent', font=(FONT, TITLE_FONT_SIZE, 'bold'))
        grade = ctk.CTkLabel(header_frame, text=str(total) + "/" + str(out_of_total), text_color=lerp_colors(GRADE_COLOR_SCALE, percentage), fg_color='transparent', font=(FONT, TITLE_FONT_SIZE, 'bold'))
        grade_percent = ctk.CTkLabel(header_frame, text=" (" + str(percentage * 100) + "%)", text_color=lerp_colors(GRADE_COLOR_SCALE, percentage), fg_color='transparent', font=(FONT, TITLE_FONT_SIZE, 'bold'))
        grade_header.pack(side='left')
        grade.pack(side='left')
        grade_percent.pack(side='left')
        header_frame.pack(padx=10, pady=10, anchor='w')
        grade_bar = ctk.CTkProgressBar(grade_frame, progress_color=lerp_colors(GRADE_COLOR_SCALE, percentage))
        grade_bar.set(percentage)
        grade_bar.pack(padx=10, pady=5, anchor='w')
        reference = ctk.CTkLabel(grade_frame, text="For this quiz, thats an " + letter_grade + " according to typical college letter grading standards", fg_color='transparent', justify='left', font=(FONT, NORMAL_FONT_SIZE))
        reference.pack(padx=10, pady=5, anchor='w')
        return_button = ctk.CTkButton(grade_frame, text="Return to question builder", fg_color=INFO, hover_color=INFO_HOVER, font=(FONT, NORMAL_FONT_SIZE), command=lambda:self.get_builder({"Domain":self.domain,"Context":self.context}, self.question_bank, self.settings, True if self.was_modified else self.ai_prop > 0))
        return_button.pack(padx=10, pady=5, anchor='w')
        grade_frame.pack(fill='x', before=self.question_nav)
            
        
class QuizQuestion(ctk.CTkFrame):
    def __init__(self, parent_frame, parent, question, index, isai, isfrq):
        super().__init__(parent_frame, fg_color=LIGHT, corner_radius=25)
        self.parent = parent
        
        # question data
        self.selected_ans = tk.StringVar()
        self.point_total = 10
        self.score = 0
        self.correct_ans = []
        self.isnumaric = True
        for key, value in question.items():
            if "C" in key:
                self.correct_ans.append(value)
                if not is_number(value) and self.isnumaric:
                    self.isnumaric = False
                
        self.explaination = question['Explaination']
        self.isfrq = True if int(question['Forced']) == 2 else (False if int(question['Forced']) == 1 else isfrq)
        self.isai = isai
        self.index = index
        self.question_data = question
        
        # create a frame for packing the question header
        self.question_header_frame = ctk.CTkFrame(self, fg_color='transparent')
        self.question_header_frame.pack(expand=True, fill='both')
        
        # draw the question header text
        self.question_header = ctk.CTkLabel(self.question_header_frame, text="Question " + str(index + 1), fg_color='transparent', font=(FONT, TITLE_FONT_SIZE, 'bold'))
        self.question_header.pack(side='left',padx=10, pady=10)
        self.flag_button = ctk.CTkButton(self.question_header_frame, text='', width=32, height=32, fg_color='transparent', hover_color=LIGHT, command=self.flag_question, image=ctk.CTkImage(Image.open(resource_path("Unflagged.png")).resize((32,32)), size=(32,32)))
        self.flag_button.pack(side='right',padx=2)
        self.point_count = ctk.CTkLabel(self.question_header_frame, text="Points: 0/" + str(self.point_total), fg_color='transparent', text_color=SELECT_BG, font=(FONT, NORMAL_FONT_SIZE))
        self.point_count.pack(side='right',padx=2)
        
        # if this is an AI generated question, draw an icon to signal such
        if(isai):
            ai_enhanced = ctk.CTkImage(Image.open(resource_path("AI Enhanced.png")).resize((32,32)), size=(32,32))
            self.ai_indicator = ctk.CTkLabel(self.question_header_frame, image=ai_enhanced, text='')
            self.ai_indicator.pack(side='left',padx=10, pady=10)
        
        # draw the question text out, and imbed when prompted
        self.question = create_embed_frame(self, question["Question"], 170, 512)
        self.question.pack(padx=5, pady=10, anchor='w')
        
        # begin with the answer choice widgets
        self.answer_choice_header = ctk.CTkLabel(self, text="Answers:", fg_color='transparent', justify='left', font=(FONT, NORMAL_FONT_SIZE))
        self.answer_choice_header.pack(padx=10, anchor='w')
        
        # branch based on being an frq question
        self.answer_widgets = []
        if not self.isfrq:
            # next branch based on having 1 or more correct answers
            if not "C2" in question.keys():
                # single correct multiple choice
                # create the radio buttons used to get the student's answer
                answer_choices = []
                answer_choices.append(ctk.CTkRadioButton(self, radiobutton_height=12, radiobutton_width=12, text=wrap_text(question["C1"], 160), variable=self.selected_ans, font=(FONT, NORMAL_FONT_SIZE), value=question["C1"], command=self.has_answer))
                for key, value in question.items():
                    if "A" in key and not "AI" in key:
                        answer_choices.append(ctk.CTkRadioButton(self, radiobutton_height=12, radiobutton_width=12, text=wrap_text(question[key], 160), variable=self.selected_ans, font=(FONT, NORMAL_FONT_SIZE), value=question[key], command=self.has_answer))
                        
                # randomly pick from the answer choices and pack in a random order
                for i in range(len(answer_choices)):
                    cur_choice = random.choice(answer_choices)
                    answer_choices.remove(cur_choice)
                    self.answer_widgets.append(cur_choice)
                    cur_choice.pack(padx=10, anchor='w')
            else:
                # multiple correct multiple choice
                # create the checkboxes used to get the student's answer
                answer_choices = []
                self.selected = []
                for key, value in question.items():
                    if ("A" in key and not "AI" in key) or "C" in key:
                        self.selected.append(tk.StringVar())
                        self.selected[-1].set("NanX")
                        answer_choices.append(ctk.CTkCheckBox(self, checkbox_height=12, checkbox_width=12, text=wrap_text(question[key], 160), variable=self.selected[-1], font=(FONT, NORMAL_FONT_SIZE), onvalue=question[key], offvalue="NanX", command=self.has_answer))
                        
                # randomly pick from the answer choices and pack in a random order
                for i in range(len(answer_choices)):
                    cur_choice = random.choice(answer_choices)
                    answer_choices.remove(cur_choice)
                    self.answer_widgets.append(cur_choice)
                    cur_choice.pack(padx=10, anchor='w')
        else:
            # single/multiple correct frq(s)
            # create free response boxes equal to the number of correct answers
            self.selected = []
            for key, value in question.items():
                if "C" in key:
                    self.selected.append(ctk.CTkTextbox(self, height=20, width=150 if self.isnumaric else 400, font=(FONT, NORMAL_FONT_SIZE)))
                    self.answer_widgets.append(self.selected[-1])
                    self.selected[-1].bind('<KeyRelease>', self.has_answer)
                    self.selected[-1].pack(padx=10, pady=5, anchor='w')

    def flag_question(self):
        # toggle the flag for this question
        if "Flag" in self.question_data:
            # unflag
            del self.question_data["Flag"]
            self.flag_button.configure(image=ctk.CTkImage(Image.open(resource_path("Unflagged.png")).resize((32,32)), size=(32,32)))
        else:
            # flag
            self.question_data["Flag"] = 'True'
            self.flag_button.configure(image=ctk.CTkImage(Image.open(resource_path("Flagged.png")).resize((32,32)), size=(32,32)))
            
                  
    def has_answer(self, event = None):
        # switch on being an frq
        if not self.isfrq:
            # switch on having 1 or more correct answers
            if not "C2" in self.question_data.keys():
                # call from a radio button, who cannot be unchecked so always will be answered
                # report this in associated button
                self.parent.question_buttons[self.index].configure(fg_color=SELECT_BG)
            else:
                # this question has an answer if its selection array isnt empty
                if not all(selected.get() == "NanX" for selected in self.selected):
                    # report having answer
                    self.parent.question_buttons[self.index].configure(fg_color=SELECT_BG)
                else:
                    # report not having answer
                    self.parent.question_buttons[self.index].configure(fg_color=BG)
        else:
            # this question has an answer if all answer fields have content
            if all(entry.get('1.0', 'end-1c') for entry in self.answer_widgets):
                # report having answer
                self.parent.question_buttons[self.index].configure(fg_color=SELECT_BG)
            else:
                # report not having answer
                self.parent.question_buttons[self.index].configure(fg_color=BG)
        
    def grade(self):
        # draw divider in question cell
        ctk.CTkFrame(self, fg_color=SELECT_BG, height=2).pack(expand=True, fill='x', padx=10, pady=2)
        
        # disable all answer widgets
        for widget in self.answer_widgets:
            widget.configure(state='disabled')
        
        # branch based on being an frq question
        if not self.isfrq:
            # next branch based on having 1 or more correct answers
            if len(self.correct_ans) == 1:
                # single correct multiple choice
                # compare the value of the selected answer against the actual correct answer
                if self.selected_ans.get() == self.correct_ans[0]:
                    # reward point total
                    self.score = self.point_total
                    
                    # reflect
                    self.point_count.configure(text="Points: " + str(self.score) + "/" + str(self.point_total))
                    
                    # pull appropriate picture
                    grade_pic = ctk.CTkImage(Image.open(resource_path("Correct Checkmark.png")).resize((96,96)), size=(96,96))
                    
                    # color button appropriately
                    self.parent.question_buttons[self.index].configure(fg_color=SUCCESS)
                    self.parent.question_buttons[self.index].configure(hover_color=SUCCESS_HOVER)
                else:
                    # pull appropriate picture
                    grade_pic = ctk.CTkImage(Image.open(resource_path("Incorrect Cross.png")).resize((96,96)), size=(96,96))
                    
                    # color button appropriately
                    self.parent.question_buttons[self.index].configure(fg_color=PRIMARY)
                    self.parent.question_buttons[self.index].configure(hover_color=PRIMARY_HOVER)
            else:
                # multiple correct multiple choice
                # get the actual selected values
                selection = []
                for var in self.selected:
                    if var.get() != "NanX":
                        selection.append(var.get())
                selection = [item for item in selection if item]
                
                # create an intersection between the correct answers list and selected lists
                intersection = [value for value in selection if value in self.correct_ans]
                
                # tabulate penalty if selection was greater than the actual number of correct answers
                penalty = max(len(selection) - len(self.correct_ans), 0)
                
                # compare the number of elements in the intersection against the total number of correct answers to reward point totals
                self.score = round(self.point_total * (max(len(intersection) - penalty, 0)/len(self.correct_ans)))
                
                # reflect
                self.point_count.configure(text="Points: " + str(self.score) + "/" + str(self.point_total))
                
                # pull appropriate picture
                if self.score / self.point_total == 1:
                    grade_pic = ctk.CTkImage(Image.open(resource_path("Correct Checkmark.png")).resize((96,96)), size=(96,96))
                    
                    # color button appropriately
                    self.parent.question_buttons[self.index].configure(fg_color=SUCCESS)
                    self.parent.question_buttons[self.index].configure(hover_color=SUCCESS_HOVER)
                elif self.score / self.point_total == 0:
                    grade_pic = ctk.CTkImage(Image.open(resource_path("Incorrect Cross.png")).resize((96,96)), size=(96,96))
                    
                    # color button appropriately
                    self.parent.question_buttons[self.index].configure(fg_color=PRIMARY)
                    self.parent.question_buttons[self.index].configure(hover_color=PRIMARY_HOVER)
                else:
                    grade_pic = ctk.CTkImage(Image.open(resource_path("Partial Equals.png")).resize((96,96)), size=(96,96))
                    
                    # color button appropriately
                    self.parent.question_buttons[self.index].configure(fg_color=PARTIAL)
                    self.parent.question_buttons[self.index].configure(hover_color=PARTIAL_HOVER)
        else:
            # single/multiple correct frq(s)
            # get the actual selected values
            selection = []
            for entry in self.selected:
                selection.append(entry.get('1.0', 'end-1c').strip().lower())
            
            # determine if we are grading by numbers or similarity
            if not self.isnumaric:
                # perform answer comparision grading between the typed answers and the correct answers
                similarities = answer_comparision_grading(selection, self.correct_ans)
            else:
                # perform numaric comparision grading between numaric answers and their most closely matching correct answers
                similarities = numaric_comparision_grading(selection, self.correct_ans)
                
            # compare the number of elements in the intersection against the total number of correct answers to reward point totals
            self.score = round(sum([self.point_total/len(selection) * x for x in similarities]))
            
            # reflect
            self.point_count.configure(text="Points: " + str(self.score) + "/" + str(self.point_total))
            
            # pull appropriate picture
            if self.score / self.point_total == 1:
                grade_pic = ctk.CTkImage(Image.open(resource_path("Correct Checkmark.png")).resize((96,96)), size=(96,96))
                    
                # color button appropriately
                self.parent.question_buttons[self.index].configure(fg_color=SUCCESS)
                self.parent.question_buttons[self.index].configure(hover_color=SUCCESS_HOVER)
            elif self.score / self.point_total == 0:
                grade_pic = ctk.CTkImage(Image.open(resource_path("Incorrect Cross.png")).resize((96,96)), size=(96,96))
                    
                # color button appropriately
                self.parent.question_buttons[self.index].configure(fg_color=PRIMARY)
                self.parent.question_buttons[self.index].configure(hover_color=PRIMARY_HOVER)
            else:
                grade_pic = ctk.CTkImage(Image.open(resource_path("Partial Equals.png")).resize((96,96)), size=(96,96))
                    
                # color button appropriately
                self.parent.question_buttons[self.index].configure(fg_color=PARTIAL)
                self.parent.question_buttons[self.index].configure(hover_color=PARTIAL_HOVER)
                
        # get the correct answers as a single string
        correct_ans_str = ""
        for i, correct_ans in enumerate(self.correct_ans):
            correct_ans_str += correct_ans
            if i != len(self.correct_ans) - 1:
                correct_ans_str += ", "
                
        # reformat
        correct_ans_str = wrap_text(correct_ans_str, 120)
                
        # create a frame for the explaination
        explaination_frame = ctk.CTkFrame(self, fg_color='transparent')
        explaination_frame.columnconfigure(0, weight=4, uniform='a')
        explaination_frame.columnconfigure(1, weight=30, uniform='a')
        explaination_frame.rowconfigure(0, weight=1, uniform='a')
        grade_label = ctk.CTkLabel(explaination_frame, image=grade_pic, text='')
        grade_label.grid(column=0, row=0, sticky='w', padx=10)
        explain_frame = ctk.CTkFrame(explaination_frame, fg_color='transparent')
        ctk.CTkLabel(explain_frame, text="Correct Answer: " + correct_ans_str, fg_color='transparent', justify='left', font=(FONT, NORMAL_FONT_SIZE)).pack(padx=10, pady=5, anchor='nw')
        
        # write the explanation with imbeds if added
        create_embed_frame(explain_frame, "Explaination: " + self.explaination, 120, 128).pack(padx=10, pady=5, anchor='nw')
        explain_frame.grid(column=1, row=0, sticky='snew', padx=10)
        explaination_frame.pack(expand=True, fill='x', padx=10)
        