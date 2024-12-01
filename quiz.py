import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
from options import *
import random
from PIL import Image
from color_lerp import *
import requests
from io import BytesIO
import matplotlib.pyplot as plt
from QAPI import *
import threading

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

def wrap_text(text, max_width):
    og_lines = text.split('\n')
    lines = []

    for line in og_lines:
        current_line = ""
        words = line.split(' ')
        for word in words:
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
    def __init__(self, parent, data, question_bank, question_count, ai_prop, frq_prop, per_page, time_limit, get_builder, modified, settings, additive_ai_questions):
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
        
        # if we are generating AI questions ontop of the original questions, add the ai_q_count BACK to the question count
        if additive_ai_questions:
            self.question_count += self.ai_q_count
        
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
            if (random.random() <= min(0.5, self.ai_prop) and ai_questions) or self.question_count - len(self.questions) == len(ai_questions):
                # pick an ai question and remove it from the ai bank
                cur_question = random.choice(ai_questions)
                ai_questions.remove(cur_question)
                roll_em = 2
            else:
                # pick a random question and remove it from the question bank
                cur_question = random.choice(self.bank)
                self.bank.remove(cur_question)
                
            # construct the question object matching that question's type!!
            match cur_question['Type']:
                case "MC":
                    self.questions.append(MultipleChoiceQuestion(self.question_frame, self, cur_question, i, roll_em == 2, roll_em <= self.frq_prop))
                case "TD":
                    self.questions.append(TermDefinitionQuestion(self.question_frame, self, cur_question, i, roll_em == 2, roll_em <= self.frq_prop))
                case "Ess":
                    self.questions.append(EssayQuestion(self.question_frame, self, cur_question, i, roll_em == 2, self.domain, self.context, self.settings))
            
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
        # Using the API, in parallel generate enough AI questions to meet the quota internally defined
        return batch_generate_questions(self.question_bank, self.ai_q_count, self.domain, self.context, self.settings["API Key"], self.settings["Model"])
        
    def grade_quiz(self, forced = False):
        # ask if the user wants to submit their quiz for sure
        if not forced and not messagebox.askyesno("Warning!", "Are you sure you want to submit your quiz for a final grade?"):
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
        n = len(self.questions)
        threads = []
        while n > 0:
            for i in range(MAX_THREADS if n // MAX_THREADS > 0 else n):
                threads.append(threading.Thread(target=self.questions[i].compute_grade))
                threads[i].start()
                print("Created thread for:", self.questions[i])
            for i in range(MAX_THREADS if n // MAX_THREADS > 0 else n):
                print(f"Waiting for thread {i}:")
                threads[i].join()
            n -= MAX_THREADS
            
        # then get the total score, but schedule the renders so they can happen concurrently?
        for question in self.questions:
            total += question.score
            out_of_total += question.point_total
            self.after(0, question.render_grade)
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
            
class MultipleChoiceQuestion(ctk.CTkFrame):
    def __init__(self, parent_frame, parent, question, index, isai, isfrq):
        super().__init__(parent_frame, fg_color=LIGHT, corner_radius=25)
        self.parent = parent
        
        # question data
        self.point_total = 10
        self.score = -1
                
        self.explaination = question['Explaination']
        self.isfrq = True if int(question['Forced']) == 2 else (False if int(question['Forced']) == 1 else isfrq)
        self.isai = isai
        self.index = index
        self.question_data = question
        self.parsed_answers = []
        
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
        self.selected = []
        if not self.isfrq:
            # next branch based on having 1 or more correct answers
            if not "C2" in question.keys():
                # the selected list functions as a singleton variable
                self.selected += [tk.StringVar()]
                
                # single correct multiple choice
                # create the radio buttons used to get the student's answer
                answer_choices = []
                answer_choices.append(ctk.CTkRadioButton(self, radiobutton_height=12, radiobutton_width=12, text=wrap_text(question["C1"], 160), variable=self.selected[0], font=(FONT, NORMAL_FONT_SIZE), value=question["C1"], command=self.has_answer))
                for key, ___ in question.items():
                    if "A" in key and not "AI" in key:
                        answer_choices.append(ctk.CTkRadioButton(self, radiobutton_height=12, radiobutton_width=12, text=wrap_text(question[key], 160), variable=self.selected[0], font=(FONT, NORMAL_FONT_SIZE), value=question[key], command=self.has_answer))
                        
                # randomly pick from the answer choices and pack in a random order
                for _ in range(len(answer_choices)):
                    cur_choice = random.choice(answer_choices)
                    answer_choices.remove(cur_choice)
                    self.answer_widgets.append(cur_choice)
                    cur_choice.pack(padx=10, anchor='w')
            else:
                # multiple correct multiple choice
                # create the checkboxes used to get the student's answer
                answer_choices = []
                for key, ___ in question.items():
                    if ("A" in key and not "AI" in key) or "C" in key:
                        self.selected.append(tk.StringVar())
                        self.selected[-1].set("NanX")
                        answer_choices.append(ctk.CTkCheckBox(self, checkbox_height=12, checkbox_width=12, text=wrap_text(question[key], 160), variable=self.selected[-1], font=(FONT, NORMAL_FONT_SIZE), onvalue=question[key], offvalue="NanX", command=self.has_answer))
                        
                # randomly pick from the answer choices and pack in a random order
                for _ in range(len(answer_choices)):
                    cur_choice = random.choice(answer_choices)
                    answer_choices.remove(cur_choice)
                    self.answer_widgets.append(cur_choice)
                    cur_choice.pack(padx=10, anchor='w')
        else:
            # single/multiple correct frq(s)
            # create free response boxes equal to the number of correct answers
            for key, val in question.items():
                if "C" in key:
                    self.selected.append(ctk.CTkTextbox(self, height=20, width=150 if is_number(val) else 400, font=(FONT, NORMAL_FONT_SIZE)))
                    self.answer_widgets.append(self.selected[-1])
                    self.selected[-1].bind('<KeyRelease>', self.has_answer)
                    self.selected[-1].pack(padx=10, anchor='w')

    def flag_question(self):
        # toggle the flag for this question
        if "Flag" in self.question_data:
            # unflag
            del self.question_data["Flag"]
            self.flag_button.configure(image=ctk.CTkImage(Image.open(resource_path("Unflagged.png")).resize((32,32)), size=(32,32)))
            if self.score == -1:
                self.has_answer()
        else:
            # flag
            self.question_data["Flag"] = 'True'
            self.flag_button.configure(image=ctk.CTkImage(Image.open(resource_path("Flagged.png")).resize((32,32)), size=(32,32)))
            if self.score == -1:
                self.parent.question_buttons[self.index].configure(fg_color=FLAG_HIGHLIGHT)
                self.parent.question_buttons[self.index].configure(hover_color=FLAG_HIGHLIGHT_HOVER)
            
                  
    def has_answer(self, event = None):
        # having a flag enabled superceeds all of these options:
        if not "Flag" in self.question_data:
            # switch on being an frq
            if not self.isfrq:
                # switch on having 1 or more correct answers
                if not "C2" in self.question_data.keys():
                    # check if a radio button has been pressed
                    if self.selected[0].get():
                        # report having answer
                        self.parent.question_buttons[self.index].configure(fg_color=SELECT_BG)
                        self.parent.question_buttons[self.index].configure(hover_color=SELECT_BG_HOVER)
                    else:
                        # report not having answer
                        self.parent.question_buttons[self.index].configure(fg_color=BG)
                        self.parent.question_buttons[self.index].configure(hover_color=BG_HOVER)
                else:
                    # this question has an answer if its selection array isnt empty
                    if not all(selected.get() == "NanX" for selected in self.selected):
                        # report having answer
                        self.parent.question_buttons[self.index].configure(fg_color=SELECT_BG)
                        self.parent.question_buttons[self.index].configure(hover_color=SELECT_BG_HOVER)
                    else:
                        # report not having answer
                        self.parent.question_buttons[self.index].configure(fg_color=BG)
                        self.parent.question_buttons[self.index].configure(hover_color=BG_HOVER)
            else:
                # this question has an answer if all answer fields have content
                if all(entry.get('1.0', 'end-1c') for entry in self.answer_widgets):
                    # report having answer
                    self.parent.question_buttons[self.index].configure(fg_color=SELECT_BG)
                    self.parent.question_buttons[self.index].configure(hover_color=SELECT_BG_HOVER)
                else:
                    # report not having answer
                    self.parent.question_buttons[self.index].configure(fg_color=BG)
                    self.parent.question_buttons[self.index].configure(hover_color=BG_HOVER)
                
        # also recompute a parsable list of answers that we use when grading now
        self.parsed_answers = [tk_string.get() for tk_string in self.selected] if not self.isfrq else [entry.get('1.0', 'end-1c') for entry in self.selected]
        
    def compute_grade(self):
        # get the score using the grading helper function implemented in the API
        self.score = grade_multiple_choice_question(self.question_data, self.parsed_answers, self.isfrq)
        
    def render_grade(self):
        # draw divider in question cell
        ctk.CTkFrame(self, fg_color=SELECT_BG, height=2).pack(expand=True, fill='x', padx=10, pady=2)
        
        # disable all answer widgets
        for widget in self.answer_widgets:
            widget.configure(state='disabled')
            
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
        correct_answers = [self.question_data[key] for key in self.question_data if key.startswith("C")]
        for i, correct_ans in enumerate(correct_answers):
            correct_ans_str += correct_ans
            if i != len(correct_answers) - 1:
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
        
class TermDefinitionQuestion(ctk.CTkFrame):
    def __init__(self, parent_frame, parent, question, index, isai, isfrq):
        super().__init__(parent_frame, fg_color=LIGHT, corner_radius=25)
        self.parent = parent
        
        # question data
        self.point_total = 10
        self.score = -1
                
        self.explaination = question['Explaination']
        self.isfrq = True if int(question['Forced']) == 2 else (False if int(question['Forced']) == 1 else isfrq)
        self.isai = isai
        self.index = index
        self.question_data = question
        self.parsed_answers = []
        
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
        self.header_frame = ctk.CTkFrame(self, fg_color='transparent')
        self.header_frame.rowconfigure(0, weight=1)
        self.header_frame.columnconfigure(0, weight=1, uniform='a')
        self.header_frame.columnconfigure(1, weight=2, uniform='a')
        self.term_header = ctk.CTkLabel(self.header_frame, text="Term:", fg_color='transparent', justify='left', font=(FONT, NORMAL_FONT_SIZE))
        self.term_header.grid(row=0, column=0, sticky='w')
        self.definition_header = ctk.CTkLabel(self.header_frame, text="Definition:", fg_color='transparent', justify='left', font=(FONT, NORMAL_FONT_SIZE))
        self.definition_header.grid(row=0, column=1, sticky='e')
        self.header_frame.pack(fill='x', expand=True, padx=10)
        
        # branch based on being an frq question
        self.answer_widgets = []
        self.selected = []
        
        # construct widgets for all the matchings listed in the question data
        terms = [self.question_data[key] for key in self.question_data if (key.startswith("T") and key != "Type")]
        matchings = len(terms)
        matching_widgets = []
        for i in range(matchings):
            # create the base frame for the matching components
            matching_frame = ctk.CTkFrame(self, fg_color='transparent')
            matching_widgets.append(matching_frame)
            matching_frame.rowconfigure(0, weight=1)
            matching_frame.columnconfigure(0, weight=1, uniform='a')
            matching_frame.columnconfigure(1, weight=2, uniform='a')
            
            # depending on if the question is frq will determine the input and how data is stored
            if self.isfrq:
                # append widget to selection, create a textbox that will be read at grade time
                self.selected.append(ctk.CTkTextbox(matching_frame, height=20, width=150, font=(FONT, NORMAL_FONT_SIZE)))
                self.selected[-1].bind('<KeyRelease>', self.has_answer)
                self.selected[-1].grid(row=0, column=0, padx=10, sticky='w')
                
                # also append to the answer widgets so we can disable it later
                self.answer_widgets.append(self.selected[-1])
            else:
                # append variable to selection
                self.selected.append(tk.StringVar())
                self.selected[-1].set("---")
                
                # create a combobox containing only the terms that belong to this question
                self.answer_widgets.append(ctk.CTkComboBox(matching_frame, font=(FONT, NORMAL_FONT_SIZE), values=["---"] + terms, command=self.has_answer, variable=self.selected[-1]))
                self.answer_widgets[-1].grid(row=0, column=0, padx=10, pady=5, sticky='w')
            definition_text = ctk.CTkLabel(matching_frame, fg_color='transparent', justify='left', text=wrap_text(self.question_data['D' + str(i + 1)], 80), font=(FONT, NORMAL_FONT_SIZE))
            definition_text.grid(row=0, column=1, padx=10, sticky='e')
            
        # shuffle the order of the matching widgets and pack them in this new order
        random.shuffle(matching_widgets)
        matching_widgets[0].pack(fill='x', expand=True, padx=10, anchor='w')
        for i in range(1, len(matching_widgets)):
            matching_widgets[i].pack(fill='x', expand=True, padx=10, anchor='w', after=matching_widgets[i-1])

    def flag_question(self):
        # toggle the flag for this question
        if "Flag" in self.question_data:
            # unflag
            del self.question_data["Flag"]
            self.flag_button.configure(image=ctk.CTkImage(Image.open(resource_path("Unflagged.png")).resize((32,32)), size=(32,32)))
            if self.score == -1:
                self.has_answer()
        else:
            # flag
            self.question_data["Flag"] = 'True'
            self.flag_button.configure(image=ctk.CTkImage(Image.open(resource_path("Flagged.png")).resize((32,32)), size=(32,32)))
            if self.score == -1:
                self.parent.question_buttons[self.index].configure(fg_color=FLAG_HIGHLIGHT)
                self.parent.question_buttons[self.index].configure(hover_color=FLAG_HIGHLIGHT_HOVER)
                  
    def has_answer(self, event = None):
        # having a flag enabled superceeds all of these options:
        if not "Flag" in self.question_data:
            # switch on being an frq
            if not self.isfrq:
                # if no combobox is empty, then this question is answered
                if not any(selected.get() == "---" for selected in self.selected):
                    # report having answer
                    self.parent.question_buttons[self.index].configure(fg_color=SELECT_BG)
                    self.parent.question_buttons[self.index].configure(hover_color=SELECT_BG_HOVER)
                else:
                    # report not having answer
                    self.parent.question_buttons[self.index].configure(fg_color=BG)
                    self.parent.question_buttons[self.index].configure(hover_color=BG_HOVER)
            else:
                # this question has an answer if all answer fields have content
                if all(entry.get('1.0', 'end-1c') for entry in self.selected):
                    # report having answer
                    self.parent.question_buttons[self.index].configure(fg_color=SELECT_BG)
                    self.parent.question_buttons[self.index].configure(hover_color=SELECT_BG_HOVER)
                else:
                    # report not having answer
                    self.parent.question_buttons[self.index].configure(fg_color=BG)
                    self.parent.question_buttons[self.index].configure(hover_color=BG_HOVER)
                
        # also recompute a parsable list of answers that we use when grading now
        self.parsed_answers = [tk_string.get() for tk_string in self.selected] if not self.isfrq else [entry.get('1.0', 'end-1c') for entry in self.selected]
        
    def compute_grade(self):
        # get the score using the grading helper function implemented in the API
        self.score = grade_matching_question(self.question_data, self.parsed_answers, self.isfrq)
        
    def render_grade(self):
        # draw divider in question cell
        ctk.CTkFrame(self, fg_color=SELECT_BG, height=2).pack(expand=True, fill='x', padx=10, pady=2)
        
        # disable all answer widgets
        for widget in self.answer_widgets:
            widget.configure(state='disabled')

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
                
        # get the term definition matchings as a single string
        matchings = sum(1 for key in self.question_data if key.startswith("D"))
        correct_match_str = ""
        for i in range(matchings):
            correct_match_str += self.question_data["T" + str(i + 1)] + ": " + self.question_data["D" + str(i + 1)]
            if i != matchings - 1:
                correct_match_str += ", "
                
        # reformat
        correct_match_str = wrap_text(correct_match_str, 120)
                
        # create a frame for the explaination
        explaination_frame = ctk.CTkFrame(self, fg_color='transparent')
        explaination_frame.columnconfigure(0, weight=4, uniform='a')
        explaination_frame.columnconfigure(1, weight=30, uniform='a')
        explaination_frame.rowconfigure(0, weight=1, uniform='a')
        grade_label = ctk.CTkLabel(explaination_frame, image=grade_pic, text='')
        grade_label.grid(column=0, row=0, sticky='w', padx=10)
        explain_frame = ctk.CTkFrame(explaination_frame, fg_color='transparent')
        ctk.CTkLabel(explain_frame, text="Correct Matchings: " + correct_match_str, fg_color='transparent', justify='left', font=(FONT, NORMAL_FONT_SIZE)).pack(padx=10, pady=5, anchor='nw')
        
        # write the explanation with imbeds if added
        create_embed_frame(explain_frame, "Explaination: " + self.explaination, 120, 128).pack(padx=10, pady=5, anchor='nw')
        explain_frame.grid(column=1, row=0, sticky='snew', padx=10)
        explaination_frame.pack(expand=True, fill='x', padx=10)
        
class EssayQuestion(ctk.CTkFrame):
    def __init__(self, parent_frame, parent, question, index, isai, domain, context, settings):
        super().__init__(parent_frame, fg_color=LIGHT, corner_radius=25)
        self.parent = parent
        
        # question data
        self.point_total = 10
        self.score = -1
                
        self.isai = isai
        self.index = index
        self.question_data = question
        self.parsed_answer = ""
        self.domain = domain
        self.context = context
        self.settings = settings
        
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
        
        # head the text segement with what kind of response that we are looking for
        self.input_box_header = ctk.CTkFrame(self, fg_color='transparent')
        match int(self.question_data["Format"]):
            case 0:
                respond_text = "Explaination:"
            case 1:
                respond_text = f"Program, written in {self.question_data["Language"]}:"
            case 2:
                respond_text = "Proof:"
        self.paragraph_header = ctk.CTkLabel(self.input_box_header, text=respond_text, fg_color='transparent', justify='left', font=(FONT, NORMAL_FONT_SIZE))
        self.paragraph_header.pack(padx=10, side='left')
        self.input_box_header.pack(expand=True, fill='x')
        
        # construct the paragraph entry widget
        self.answer_widget = ctk.CTkTextbox(self, height=150, width=600, font=(FONT, NORMAL_FONT_SIZE))
        self.answer_widget.bind('<KeyRelease>', self.has_answer)
        self.answer_widget.pack(fill='x', expand=True, padx=10, pady=5, anchor='w')

    def flag_question(self):
        # toggle the flag for this question
        if "Flag" in self.question_data:
            # unflag
            del self.question_data["Flag"]
            self.flag_button.configure(image=ctk.CTkImage(Image.open(resource_path("Unflagged.png")).resize((32,32)), size=(32,32)))
            if self.score == -1:
                self.has_answer()
        else:
            # flag
            self.question_data["Flag"] = 'True'
            self.flag_button.configure(image=ctk.CTkImage(Image.open(resource_path("Flagged.png")).resize((32,32)), size=(32,32)))
            if self.score == -1:
                self.parent.question_buttons[self.index].configure(fg_color=FLAG_HIGHLIGHT)
                self.parent.question_buttons[self.index].configure(hover_color=FLAG_HIGHLIGHT_HOVER)
            
                  
    def has_answer(self, event = None):
        # having a flag enabled superceeds all of these options:
        if not "Flag" in self.question_data:
            # this question has an answer if the paragraph field has content
            if self.answer_widget.get('1.0', 'end-1c'):
                # report having answer
                self.parent.question_buttons[self.index].configure(fg_color=SELECT_BG)
                self.parent.question_buttons[self.index].configure(hover_color=SELECT_BG_HOVER)
            else:
                # report not having answer
                self.parent.question_buttons[self.index].configure(fg_color=BG)
                self.parent.question_buttons[self.index].configure(hover_color=BG_HOVER)
                
        # also push the text box content 
        self.parsed_answer = self.answer_widget.get('1.0', 'end-1c')
        
    def compute_grade(self):
        # check if we are in offline mode, as we cannot grade the question due to its dependence on an API call!
        if not self.settings['Offline']:
            # get the score using the grading helper function implemented in the API
            self.score = grade_essay_question(self.question_data, self.parsed_answer, self.domain, self.context, self.settings["API Key"], self.settings["Model"])
        else:
            # default to perfect score
            self.score = 10
        
    def render_grade(self):
        # draw divider in question cell
        ctk.CTkFrame(self, fg_color=SELECT_BG, height=2).pack(expand=True, fill='x', padx=10, pady=2)
        
        self.answer_widget.configure(state='disabled')

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
                
        # create a frame for the explaination
        explaination_frame = ctk.CTkFrame(self, fg_color='transparent')
        explaination_frame.columnconfigure(0, weight=4, uniform='a')
        explaination_frame.columnconfigure(1, weight=30, uniform='a')
        explaination_frame.rowconfigure(0, weight=1, uniform='a')
        grade_label = ctk.CTkLabel(explaination_frame, image=grade_pic, text='')
        grade_label.grid(column=0, row=0, sticky='w', padx=10)
        explain_frame = ctk.CTkFrame(explaination_frame, fg_color='transparent')
        ctk.CTkLabel(explain_frame, text="Guidelines: " + wrap_text(self.question_data["Guidelines"], 120), fg_color='transparent', justify='left', font=(FONT, NORMAL_FONT_SIZE)).pack(padx=10, pady=5, anchor='nw')
        
        # write the explanation with imbeds if added
        create_embed_frame(explain_frame, "Explaination: " + self.question_data["Explaination"], 120, 128).pack(padx=10, pady=5, anchor='nw')
        explain_frame.grid(column=1, row=0, sticky='snew', padx=10)
        explaination_frame.pack(expand=True, fill='x', padx=10)
        
        # clear the explaination
        self.question_data["Explaination"] = "Essay questions cannot be graded in offline mode, but I'm sure you got it right :)"