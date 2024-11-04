import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
from tkinter import filedialog
from options import *
from openai import OpenAI
from PIL import Image, ImageFont
import json
import random
import requests
from QAPI import *

def remove_backticked_imbeds(s):
    # split the input based on backticked imbeds
    imbeds = s.split('```')
    result = ""
    
    # iterate through the imbeds
    for i, chunk, in enumerate(imbeds):
        if i % 2 == 0:
            # not an imbed, skip
            result += chunk
        else:
            # add if not an image imbed
            if not chunk.startswith("img:"):
                result += "```" + chunk + "```"
    
    return result

def measure_text_width(text):
    font = ImageFont.truetype(resource_path('tahoma.ttf'), NORMAL_FONT_SIZE)
    return font.getlength(text)
    
def adjust_textbox_height(event, textbox, limit, variable):
    # Calculate the number of lines in the textbox
    lines = event.widget.get('1.0', 'end-1c').split('\n')
    # From this, calculate the width that each line takes to render
    characters = [measure_text_width(s) for s in lines]
    
    # Define the character limit per line
    char_limit_per_line = limit # Adjust this value as needed
    
    # Calculate the number of lines needed
    char_lines = sum([c // char_limit_per_line for c in characters])
    
    # Calculate the new height needed for the textbox
    new_height = min(max(len(lines) + char_lines + 1, 1), 8) * 15 # Adjust the multiplier as needed
    
    # Update the height of the textbox
    textbox.configure(height=new_height)
    
    # Get the text of the textbox and send it to the variable
    variable.set(event.widget.get('1.0', 'end-1c'))
    
def force_update_textbox_height(textbox, limit, value):
    # Calculate the number of lines in the textbox
    lines = value.split('\n')
    # Also calculate the number of characters in the textbox
    characters = [measure_text_width(s) for s in lines]
    
    # Define the character limit per line
    char_limit_per_line = limit # Adjust this value as needed
    
    # Calculate the number of lines needed
    char_lines = sum([c // char_limit_per_line for c in characters])
    
    # Calculate the new height needed for the textbox
    new_height = min(max(len(lines) + char_lines + 1, 1), 8) * 15 # Adjust the multiplier as needed
    
    # Update the height of the textbox
    textbox.configure(height=new_height)

class Builder(ctk.CTkFrame):
    def __init__(self, parent, context_data, get_mainmenu, content_data, get_quiz, start_modified, settings):
        super().__init__(parent, fg_color='transparent')
        
        # external
        self.get_quiz = get_quiz
        self.get_mainmenu = get_mainmenu
        self.parent = parent
        self.settings = settings
        
        # data
        self.imported_content = content_data
        self.saved_questions = []
        self.q_count = tk.IntVar()
        self.q_count.set(0)
        self.context = context_data['Context']
        self.domain = context_data['Domain']
        self.filepath = ""
        self.modified = start_modified
        
        # format
        self.columnconfigure(0, weight=2, uniform='a')
        self.columnconfigure(1, weight=5, uniform='a')
        self.rowconfigure(0, weight=1)
        
        # create simple frames to contain objects in within the grid
        self.question_builder_frame = ctk.CTkFrame(self, fg_color='transparent', corner_radius=0)
        self.question_builder_frame.grid(row = 0, column = 1, sticky='snew', padx=20, pady=20)
        self.question_preview_frame_bg = ctk.CTkFrame(self, fg_color='transparent', corner_radius=0)
        self.question_preview_frame_bg.grid(row = 0, column = 0, sticky='snew')
        self.question_preview_frame = ctk.CTkFrame(self, fg_color=DARK, corner_radius=0)
        self.question_preview_frame.place(relheight=1, relwidth=0.25)
        self.question_scroll_view = ctk.CTkScrollableFrame(self.question_preview_frame, fg_color='transparent')
        self.question_scroll_view.pack(expand=True, fill='both')
        self.save_deck_button = ctk.CTkButton(self.question_preview_frame, fg_color=SUCCESS, hover_color=SUCCESS_HOVER, font=(FONT, NORMAL_FONT_SIZE), text='Save Deck', command=self.save_deck, width=80)
        self.save_deck_button.pack(side='left', anchor='s')
        self.parent.bind('<Control-s>', self.save_deck)
        self.save_deck_button = ctk.CTkButton(self.question_preview_frame, fg_color=SUCCESS, hover_color=SUCCESS_HOVER, font=(FONT, NORMAL_FONT_SIZE), text='Save Deck As', command=self.save_deck_as, width=80)
        self.save_deck_button.pack(side='left', anchor='s')
        self.parent.bind('<Control-S>', self.save_deck_as)
        self.exit_deck_button = ctk.CTkButton(self.question_preview_frame, fg_color=PRIMARY, hover_color=PRIMARY_HOVER, font=(FONT, NORMAL_FONT_SIZE), text='Exit Deck', command=self.exit_deck, width=80)
        self.exit_deck_button.pack(side='left', anchor='s')
        self.parent.bind('<Control-w>', self.exit_deck)
        
        # draw the question field
        self.builder_frame = BuilderFrame(self.question_builder_frame, self, self.question_scroll_view, (self.domain, self.context), self.settings)
        
        # draw the quiz setup field
        self.quiz_frame = QuizFrame(self.question_builder_frame, self, self.get_quiz, self.settings)
        
        # check if we have question data to convert into side frames
        if self.imported_content:
            # iterate through the saved question dictonaries
            for question_data in self.imported_content:
                # create a clickable reference in the side menu that contains this information
                self.saved_questions.append(QuestionFrame(self.question_scroll_view, self, self.builder_frame, question_data))
            
                # inc question count
                self.q_count.set(self.q_count.get() + 1)
                
                # get the next index for the question
                self.builder_frame.q_index = self.q_count.get() + 1
                self.builder_frame.question_index.set('Question ' + str(self.builder_frame.q_index))
                
        # pack to take the entire window
        self.pack(expand=True, fill='both')
        
    def exit_deck(self, event = None):
        # check if this deck has been modified since last save
        if self.modified:
            # prompt warning and allow for saving
            if(messagebox.askyesno("Wait Up", "You have modified this deck since its last save, do you want to save it quick before exiting?")):
               # call save deck, if it fails exit
               if not self.save_deck():
                   return
               
        # first remove any binds set on the parent window
        self.parent.unbind('<Control-s>')
        self.parent.unbind('<Control-S>')
        self.parent.unbind('<Control-w>')
        
        # get the main menu and discard this builder frame
        self.get_mainmenu()
        
    def save_deck_as(self, event = None):
        # assume we dont have a file path
        file_path = filedialog.asksaveasfile(initialfile=f'{self.domain}.qizy', mode='w', defaultextension='.qizy', filetypes=[("Quizzy Files", "*.qizy"), ("All Files", "*.*")]).name # File dialog to get a file path to save at
        
        if file_path: # Check if the file path is valid
            # update save path
            self.filepath = file_path
            
            # continue to the save deck function
            self.save_deck()
        else:
            messagebox.showerror("Unkown?", "There was an issue saving this deck to that location!")
        
    def save_deck(self, event = None):
        # check if we need to get a save path since this is the first time saving the deck
        if self.filepath == "":
            file_path = filedialog.asksaveasfile(initialfile=f'{self.domain}.qizy', mode='w', defaultextension='.qizy', filetypes=[("Quizzy Files", "*.qizy"), ("All Files", "*.*")]).name # File dialog to get a file path to save at
            
            if file_path: # Check if the file path is valid
                # update save path
                self.filepath = file_path
            else:
                messagebox.showerror("Unknown?", "There was an issue saving this deck to that location!")
                self.filepath = ""
                return False
                
        # check afterwards if we have a valid file path
        if self.filepath != "":
            # get a list of question data from the question frames
            data = []
            for question_frame in self.saved_questions:
                data.append(question_frame.content)
            
            # prune from saved questions any entries used for flag purposes
            for question in data:
                for key, ___ in question.items():
                    if key == "Flag" or key == "AI Generated":
                        del data[key]
            
            # create a save file dictionary
            save = {"Domain":self.domain,
                    "Context":self.context,
                    "Data":data}
            
            # export to JSON file
            json_data = json.dumps(save, indent=4)
            with open(self.filepath, 'w', encoding='utf-8') as export:
                # write to destination
                export.write(json_data)
                        
            self.modified = False            
            
            return True
        return False
 
class QuizFrame(ctk.CTkFrame):
    def __init__(self, parent_frame, parent, get_quiz, settings):
        super().__init__(parent_frame, fg_color=LIGHT, corner_radius=25)
        
        # exterior references
        self.parent = parent
        self.get_quiz = get_quiz
        self.settings = settings
        
        # data
        self.question_count = tk.IntVar()
        self.question_count.set(0)
        self.question_count_amount = tk.StringVar()
        self.question_count_amount.set("0")
        self.per_page = tk.IntVar()
        self.per_page.set(1)
        self.per_page_amount = tk.StringVar()
        self.per_page_amount.set("1")
        self.frq_prop = tk.DoubleVar()
        self.frq_prop.set(0)
        self.frq_prop_amount = tk.StringVar()
        self.frq_prop_amount.set("0")
        self.timer = tk.IntVar()
        self.timer.set(0)
        self.timer_amount = tk.StringVar()
        self.timer_amount.set("0")
        self.quiz_condition = self.parent.q_count.get() < 3
        
        # create trace for question change condition
        self.parent.q_count.trace_add('write', self.check_for_valid_gen)
        
        # inital draw check
        self.check_for_valid_gen()
        
        # pack
        self.pack(ipadx=20, fill='x', padx=20, pady=20) 
        
    def make_quiz(self, ai_setting):
        # if the ai_setting is > 0, prompt for saving first since the program could crash
        if(ai_setting > 0 and messagebox.askyesno("Thought you should know!", "Prompting may cause the program to crash and lose your changes so far, so its recommended to save first before generating a quiz with AI enhanced questions!")):
            # call save deck, if it fails exit
            if not self.parent.save_deck():
                return
        
        # package everything up to send to the quiz builder
        data = (self.parent.domain, self.parent.context)
        content = []
        for question in self.parent.saved_questions:
            content.append(question.content)
        counts = (self.question_count.get(), self.frq_prop.get(), round(ai_setting * 33.3) / 100.0, self.per_page.get(), self.parent.modified, self.timer.get())
        
        # quickly place in the overall builder a disclaimer
        cover = ctk.CTkFrame(self.parent, fg_color=BG, corner_radius=0)
        paitence_frame = ctk.CTkFrame(cover, fg_color=LIGHT, corner_radius=0)
        header = ctk.CTkLabel(paitence_frame, text="Making your quiz!", fg_color='transparent', font=(FONT, TITLE_FONT_SIZE, 'bold'))
        header.pack(expand=True, fill='x', padx=10, pady=5)
        explaination = ctk.CTkLabel(paitence_frame, text='Rendering quiz elements and prompting for questions takes a bit, \nbut this shouldn\'t take longer than a minute!', font=(FONT, NORMAL_FONT_SIZE))
        explaination.pack(expand=True, fill='x', padx=10, pady=5)
        paitence_frame.place(anchor='center', rely=0.5, relx=0.5)
        cover.place(anchor='center', relwidth=1, relheight=1, rely=0.5, relx=0.5)
        
        # send to the quiz builder
        self.after(100, lambda:self.get_quiz(data, content, counts, self.settings))
        
    def check_for_valid_gen(self, *args):
        # check if this change in question count changes the quiz condition
        condition_changed = self.quiz_condition != (self.parent.q_count.get() >= 3)
        print(self.quiz_condition)
        print(self.parent.q_count.get() >= 3)
        
        # if we are on a question count of 3 or 4, due to edge case auto flag condition changed
        if(self.parent.q_count.get() == 3 or self.parent.q_count.get() == 4):
            condition_changed = True
        
        print(condition_changed)
        
        if(condition_changed):
            # check if we have a valid number of questions to generate a practice quiz
            if(self.parent.q_count.get() < 3):
                print("Failed race condition")
                for child in self.winfo_children():
                    child.destroy()
                
                # undraw the contents of the quiz frame
                self.draw_quiz_frame(False)
            else:
                print("Pass race condition")
                for child in self.winfo_children():
                    child.destroy()
                
                # draw the contents of the quiz frame
                self.draw_quiz_frame(True)
                
                # enable the buttons (if online for ai buttons)
                for i, button in enumerate(self.gen_test_buttons):
                    if self.settings['Offline'] and i != 0:
                        button.configure(state='disabled')
                    else:
                        button.configure(state='normal')
                        
        # push new condition status
        self.quiz_condition = self.parent.q_count.get() >= 3
                    
    def draw_quiz_frame(self, state):
        # check if we are drawing the contents of the quiz frame
        if state:
            # settings widgets for creating a new quiz
            self.quiz_maker_label = ctk.CTkLabel(self, text="Start a Practice Quiz", fg_color='transparent', font=(FONT, TITLE_FONT_SIZE, 'bold'))
            self.quiz_maker_label.pack(padx=10, pady=10, anchor='w')
            
            # slider for question count
            self.question_count.set(3)
            if self.parent.q_count.get() != 3:
                self.question_count_frame = ctk.CTkFrame(self, fg_color='transparent')
                self.q_count_label = ctk.CTkLabel(self.question_count_frame, text="Num Questions: ", fg_color='transparent', font=(FONT, NORMAL_FONT_SIZE))
                self.q_count_label.pack(side='left', expand=True, fill='x', padx=10, pady=3)
                self.q_count_amnt = ctk.CTkTextbox(self.question_count_frame, font=(FONT, NORMAL_FONT_SIZE), height=20)
                self.q_count_amnt.insert(tk.END, self.question_count_amount.get())
                self.q_count_slider = ctk.CTkSlider(self.question_count_frame, from_=3, to=self.parent.q_count.get(), variable=self.question_count, command=lambda x:self.get_new_amount(self.q_count_amnt, self.question_count, self.question_count_amount))
                self.q_count_slider.pack(side='left', expand=True, fill='x', padx=10, pady=3)
                self.q_count_amnt.pack(side='left', expand=True, fill='x', padx=10, pady=3)
                self.q_count_amnt.bind("<KeyRelease>", lambda x:self.attempt_pushing_textbox_amount(self.q_count_amnt, self.question_count, self.question_count_amount, 0))
                self.question_count_frame.pack(padx=10, pady=3)
            
            # slider for questions per page
            self.per_page_frame = ctk.CTkFrame(self, fg_color='transparent')
            self.p_count_label = ctk.CTkLabel(self.per_page_frame, text="Qs per Page: ", fg_color='transparent', font=(FONT, NORMAL_FONT_SIZE))
            self.p_count_label.pack(side='left', expand=True, fill='x', padx=10, pady=3)
            self.p_count_amnt = ctk.CTkTextbox(self.per_page_frame, font=(FONT, NORMAL_FONT_SIZE), height=20)
            self.p_count_amnt.insert(tk.END, self.per_page_amount.get())
            self.p_count_slider = ctk.CTkSlider(self.per_page_frame, from_=1, to=self.question_count.get() if self.question_count.get() < 50 else 50, variable=self.per_page, command=lambda x:self.get_new_amount(self.p_count_amnt, self.per_page, self.per_page_amount))
            self.p_count_slider.pack(side='left', expand=True, fill='x', padx=10, pady=3)
            self.p_count_amnt.pack(side='left', expand=True, fill='x', padx=10, pady=3)
            self.p_count_amnt.bind("<KeyRelease>", lambda x:self.attempt_pushing_textbox_amount(self.p_count_amnt, self.per_page, self.per_page_amount, 1))
            self.per_page_frame.pack(padx=10, pady=3)
            
            # slider for frq proportion
            self.frq_prop_frame = ctk.CTkFrame(self, fg_color='transparent')
            self.frq_prop_label = ctk.CTkLabel(self.frq_prop_frame, text="FRQ Percentage: ", fg_color='transparent', font=(FONT, NORMAL_FONT_SIZE))
            self.frq_prop_label.pack(side='left', expand=True, fill='x', padx=10, pady=3)
            self.frq_prop_amnt = ctk.CTkTextbox(self.frq_prop_frame, font=(FONT, NORMAL_FONT_SIZE), height=20)
            self.frq_prop_amnt.insert(tk.END, self.frq_prop_amount.get())
            self.frq_prop_slider = ctk.CTkSlider(self.frq_prop_frame, from_=0, to=100, variable=self.frq_prop, command=lambda x:self.get_new_amount(self.frq_prop_amnt, self.frq_prop, self.frq_prop_amount))
            self.frq_prop_slider.pack(side='left', expand=True, fill='x', padx=10, pady=3)
            self.frq_prop_amnt.pack(side='left', expand=True, fill='x', padx=10, pady=3)
            self.frq_prop_amnt.bind("<FocusOut>", lambda x:self.attempt_pushing_textbox_amount(self.frq_prop_amnt, self.frq_prop, self.frq_prop_amount, 2))
            self.frq_prop_frame.pack(padx=10, pady=3)
            
            # entry for timer
            self.timer_frame = ctk.CTkFrame(self, fg_color='transparent')
            self.timer_label = ctk.CTkLabel(self.timer_frame, text="Time limit (in mins): ", fg_color='transparent', font=(FONT, NORMAL_FONT_SIZE))
            self.timer_label.pack(side='left', expand=True, fill='x', padx=10, pady=3)
            self.timer_frame_amnt = ctk.CTkTextbox(self.timer_frame, font=(FONT, NORMAL_FONT_SIZE), height=20)
            self.timer_frame_amnt.insert(tk.END, self.timer_amount.get())
            self.timer_frame_amnt.pack(side='left', expand=True, fill='x', padx=10, pady=3)
            self.timer_frame_amnt.bind("<KeyRelease>", lambda x:self.attempt_pushing_textbox_amount(self.timer_frame_amnt, self.timer, self.timer_amount, 3))
            self.timer_frame.pack(padx=10, pady=3)
            
            # buttons for ai test formats
            self.explaination = ctk.CTkLabel(self, text='Pick a format to generate a test with these settings:', font=(FONT, NORMAL_FONT_SIZE))
            self.explaination.pack(pady=2.5)
            self.ai_gen_test_frame = ctk.CTkFrame(self, fg_color='transparent')
            self.gen_test_buttons = []
            text_set = ('Rehersed\n(0% generated)', 'Familiar\n(33% generated)', 'Foreign\n(66% generated)', 'Unique\n(100% generated)')
            color_set = (SUCCESS, WARNING, DANGER, PRIMARY)
            hover_color_set = (SUCCESS_HOVER, WARNING_HOVER, DANGER_HOVER, PRIMARY_HOVER)
            for i in range(4):
                # create the button
                self.gen_test_buttons.append(ctk.CTkButton(self.ai_gen_test_frame, text=text_set[i], fg_color=color_set[i], hover_color=hover_color_set[i], font=(FONT, NORMAL_FONT_SIZE), width=80, height=56, command=lambda x=i:self.make_quiz(x)))
                self.gen_test_buttons[i].pack(side='left', expand=True, fill='x', padx=10, pady=5)
            self.ai_gen_test_frame.pack(padx=10, pady=10)
            
            # create dynamic trace
            self.parent.q_count.trace_add('write', self.update_sliders)
            self.question_count.trace_add('write', self.update_sliders)
            self.update_sliders()
        else:
            # only draw label stating we need 3 questions
            self.quiz_maker_label = ctk.CTkLabel(self, text="Create at least 3 questions to start a quiz!", fg_color='transparent', font=(FONT, TITLE_FONT_SIZE, 'bold'))
            self.quiz_maker_label.pack(padx=10, pady=10, anchor='w')
        
    def get_new_amount(self, textbox, num_var, str_var):
        # write the amount to the string var holding the question count selected
        str_var.set(str(num_var.get()))
        
        # reflect in textbox
        textbox.delete(1.0, tk.END)
        textbox.insert(tk.END, str_var.get())
        
    def attempt_pushing_textbox_amount(self, textbox, num_var, str_var, typeref):
        def is_float(s):
            try:
                float_val = float(s)
                return '.' in s
            except ValueError:
                return False
        
        # get the textbox's contents
        contents = textbox.get('1.0', 'end-1c').strip()
        
        # validate the textbox's contents being a digit
        if (contents.isdigit() and (typeref == 0 or typeref == 1 or typeref == 3)) or (is_float(contents) and typeref == 2):
            # convert and place within bounds
            new_amnt = int(contents) if (typeref == 0 or typeref == 1 or typeref == 3) else float(contents)
            new_amnt = max(3 if typeref == 0 else 1 if typeref == 1 else 0, min(new_amnt, self.parent.q_count.get() if typeref == 0 else self.question_count.get() if typeref == 1 else 100 if typeref == 2 else 9999))
            
            # relect in integer and string variables
            str_var.set(str(new_amnt))
            num_var.set(new_amnt)
            
        # rewrite back to the textbox
        textbox.delete(1.0, tk.END)
        textbox.insert(tk.END, str_var.get())
    
    def update_sliders(self, *args):
        # update the to/from of the sliders where needed
        if self.parent.q_count.get() != 3:
            self.q_count_slider.configure(to=self.parent.q_count.get())
        self.p_count_slider.configure(to=self.question_count.get() if self.question_count.get() < 50 else 50)
        
        # set the amount in question count to its maximum is it is exceeded
        if self.parent.q_count.get() != 3:
            if self.question_count.get() > self.parent.q_count.get():
                self.question_count.set(self.parent.q_count.get())
                self.question_count_amount.set(str(self.parent.q_count.get()))
                self.attempt_pushing_textbox_amount(self.q_count_amnt, self.question_count, self.question_count_amount, 0)
        if self.per_page.get() > self.question_count.get():
            self.per_page.set(self.question_count.get() if self.question_count.get() < 50 else 50)
            self.per_page_amount.set(str(self.per_page.get()))
            self.attempt_pushing_textbox_amount(self.p_count_amnt, self.per_page, self.per_page_amount, 1)
            
        # lastly update the slider positions
        if self.parent.q_count.get() != 3:
            self.q_count_slider.set(self.question_count.get())
        self.p_count_slider.set(self.per_page.get())
        
class BuilderFrame(ctk.CTkFrame):
    def __init__(self, parent_frame, parent, question_preview_frame, background, settings):
        super().__init__(parent_frame, fg_color=LIGHT, corner_radius=25)
        
        # exterior references
        self.parent = parent
        self.question_preview_frame = question_preview_frame
        self.settings = settings
        
        # data
        self.q_index = 1
        self.question_index = tk.StringVar()
        self.question_index.set('Question ' + str(self.q_index))
        self.background = background
        self.refresh_explaination_flag = False
        self.is_modified = False
        
        # format the frame to have a selector and a question render field
        self.columnconfigure(0, weight=2, uniform='a')
        self.columnconfigure(1, weight=1, uniform='a')
        self.rowconfigure(0, weight=1, uniform='b')
        self.rowconfigure(1, weight=1, uniform='b')
        self.rowconfigure(2, weight=1, uniform='b')
        
        self.question_label = ctk.CTkLabel(self, text="Question #", fg_color='transparent', font=(FONT, TITLE_FONT_SIZE, 'bold'), textvariable=self.question_index)
        self.question_label.pack(padx=10, pady=10, anchor='w')
        
        # create the frame that will contain the question entry information
        self.question_frame = ctk.CTkFrame(self, fg_color='transparent')
        self.question_frame.pack(fill='both', expand=True, padx=10, pady=10)
        #self.content = ctk.CTkFrame(self.question_frame, fg_color='transparent')
        
        # create a button to submit this question's format
        self.submit_question_button = ctk.CTkButton(self, fg_color=SECONDARY, hover_color=SECONDARY_HOVER, text='Submit Question', font=(FONT, NORMAL_FONT_SIZE), height=28, command=self.submit_question)
        self.submit_question_button.pack(fill='x', expand=True, padx=10, pady=10)
        self.refresh_explaination = None
        self.confirm_explaination = None
        self.explain_frame = None
        
        # create a frame for the question entry
        self.question = MultipleChoice(self.question_frame, self.modified)
        self.is_modified = False
        
        self.pack(ipadx=20, fill='x', padx=20, pady=20) 
        
    def enable_explaination_refresh(self):
        # reset the state of the explaination refresh button
        self.reset_explaination_refresh()
        
        # check if we still need an explaination for this question
        if(not self.settings['Offline'] and self.question.explaination == "No explaination was generated :("):
            # force the refresh since we still need an explaination
            self.confirm_explaination = ctk.CTkLabel(self, text_color=PRIMARY, text='!!! This question is missing its explaination, please submit !!!', font=(FONT, NORMAL_FONT_SIZE, 'bold'))
            self.confirm_explaination.pack(fill='x', expand=True, padx=10, pady=10, before=self.submit_question_button)
            
            # flag
            self.refresh_explaination_flag = True
        else:
            # create the button that allows for a refresh (if not offline)
            if not self.settings['Offline']:
                image = Image.open(resource_path("Enhanced.png")).resize((22,22))
                self.refresh_explaination = ctk.CTkButton(self, image=ctk.CTkImage(image), fg_color=DANGER, hover_color=DANGER_HOVER, text='Refresh Explaination', font=(FONT, NORMAL_FONT_SIZE), height=28, command=self.refresh)
                self.refresh_explaination.pack(fill='x', expand=True, padx=10, pady=10, before=self.submit_question_button)
            
            # additionally create a field that allows the user to overwrite the explaination field
            # create a frame for the question entry
            self.explain_frame = ctk.CTkFrame(self, fg_color='transparent')
            self.explain_frame.columnconfigure(0, weight=3)
            self.explain_frame.columnconfigure(1, weight=12)
            self.explain_frame.rowconfigure(0,weight=1)
            self.explain_frame_label = ctk.CTkLabel(self.explain_frame, text="Explaination: ", fg_color='transparent', font=(FONT, NORMAL_FONT_SIZE))
            self.explain_frame_label.grid(row=0, column=0, sticky='nw', pady=10)
            self.explain_frame_entry = ctk.CTkTextbox(self.explain_frame, font=(FONT, NORMAL_FONT_SIZE), height=20)
            self.explain_frame_entry.grid(column=1, row=0, sticky='ew')
            self.explain_frame_entry.bind('<KeyRelease>', self.push_to_explaination)
            self.explain_frame.pack(fill='x', padx=10, pady=10, before=self.submit_question_button)
            
            # fill in the field content with the existing explaination
            self.explain_frame_entry.insert(tk.END, self.question.explaination)
            force_update_textbox_height(self.explain_frame_entry, 465, self.question.explaination)
        
    def refresh(self):
        # delete the button, replace with label confirming action
        self.refresh_explaination.destroy()
        self.confirm_explaination = ctk.CTkLabel(self, text_color=DANGER, text='The explaination will be refreshed on update', font=(FONT, NORMAL_FONT_SIZE))
        
        # place before the explain frame if it exists
        if self.explain_frame:    
            self.confirm_explaination.pack(fill='x', expand=True, padx=10, pady=10, before=self.explain_frame)
        else:
            self.confirm_explaination.pack(fill='x', expand=True, padx=10, pady=10, before=self.submit_question_button)
        
        # if there is an explain entry, disable it
        if self.explain_frame:
            self.explain_frame_entry.configure(state='disabled')
    
        # flag
        self.refresh_explaination_flag = True
        
    def reset_explaination_refresh(self):
        # reset everything related to explaination refresh
        self.refresh_explaination_flag = False
        if self.confirm_explaination:
            self.confirm_explaination.destroy()
        if self.refresh_explaination:
            self.refresh_explaination.destroy()
        if self.explain_frame:
            self.explain_frame.destroy()
            
    def get_image_embed_links_if_any(self, question):
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
                                
    def submit_question(self):
        # check that the question field has content
        if(len(self.question.question_entry.get('1.0', 'end-1c')) < 1):
            # prompt window stating that the question at least requires a question
            messagebox.showwarning("Hold Up!", "You need to at least define a question before you can submit this to your deck!")
            
            return
        
        # create the submission dictionary
        submit_list = {}
        
        # collate the contents of the question fields into a dictionary of strings based on the fields read, each string will be prefixed with its key
        submit_list['Q'] = str(self.q_index)
        for i, field_var in enumerate(self.question.gui_held_information):
            if i == 0:
                submit_list["Question"] = field_var.get()
            elif i <= self.question.correct_answers:
                submit_list["C" + str(i)] = field_var.get()
            else:
                submit_list["A" + str(i - self.question.correct_answers)] = field_var.get()
        submit_list['Explaination'] = self.question.explaination
        submit_list['Forced'] = str(self.question.forced.get())
        
        # check if we have at least one correct answer and one incorrect answer if we are offline
        if self.settings['Offline'] and (not "C1" in submit_list or not "A1" in submit_list):
            messagebox.showwarning("Offline!", "Sorry, since you are in offline mode you must provide at least one correct and incorrect answer to the question before you can submit it to your deck!")
            
            return
        
        # if offline inform about no automatic explaination generation
        if self.settings['Offline'] and submit_list['Explaination'].strip() == '':
            messagebox.showinfo("Offline!", "Heads up, inital explaination generation isnt performed in offline mode. Please reedit this question if you would like to provide an explaination of your own!")
            
            submit_list['Explaination'] = "No explaination was generated :("
        
        # skip calls if offline
        if not self.settings['Offline']:
            # MAKE CALLS TO CHATGPT FOR MISSING FIELDS HERE
            # set the assistant up here
            client = OpenAI(api_key=self.settings['API Key'])
            domain = "Domain: " + self.background[0] + "\n"
            model = "gpt-4o-mini" if self.settings['Model'] == '3.5' else "gpt-4o"
            
            # we define the context by selecting a random span of context cut words from said context
            context_words = self.background[1].split(" ")
            start_point = random.choice(range(0, max(len(context_words) - int(self.settings['ContextCut']), 1)))
            context = "Context: " + " ".join(context_words[start_point:min(start_point+int(self.settings['ContextCut']), len(context_words))]) + "\n"
            img_link = self.get_image_embed_links_if_any(submit_list['Q'])
            system_img = """Use the image that you are provided to aid in constructing your response.""" if img_link != "" else ""
            
            # determine if we need answer choices
            if not "C1" in submit_list.keys() and not "A1" in submit_list.keys():
                # set the environment up
                system = """You are an assistant knowledgeable in many academic subjects. In particular, the user is a student who will specify what domain they request that you fetch knowledge from, while also providing a small paragraph of context that helps you generate helpful responses for the user.

                            In particular, your responses are tailored to generating practice test questions, whether that be filling in missing parts of user-created questions such as picking correct answers, generating incorrect answers, or writing an explanation as to why the correct answer is the correct answer. You will also be providing full-on new practice questions for the user to practice with based on a subset of questions picked and the ascribed domain and context be provided with every input.

                            The input you receive will also be minimal to help with processing and costs associated. You will ALWAYS be given a domain, denoted with the prefix "Domain:" for which the question comes from. In addition, you will ALWAYS be given a subset of "Context:" for which you should prioritize when synthesizing your answer. Lastly, you will receive one of the following:
                            - A question followed by a request for answer choices (provide a correct answer and 3 incorrect answer choices in that order, side note, if you anticipate the question is a true or false question, then only specify 1 correct answer and 1 incorrect answer)
                                - Ex. output 1:
                                    C~ They can be assigned to variables, passed as arguments, and returned as values.
                                    I~ They can only be assigned to variables and stored in data structures
                                    I~ They can only be passed as arguments to other functions
                                    I~ They can only be returned as values from other functions
                                - Ex. output 2:
                                    C~ True
                                    I~ False
                            
                            Since your output will be fed directly to a program to be parsed, you MUST be STRICT with what you output, and be as BRIEF as possible. for ALL outputs, your responses MUST ADHERE TO THE ABOVE FORMAT NO MATTER WHAT
                            
                            Please keep in mind you are free to use any characters in your response as the delimiters will help the program figure out what field means what."""
                
                # get the required context for the prompt
                background = remove_backticked_imbeds(submit_list["Question"]) + "\n"
                request = "Please provide answer choices for this question"
                
                # prompt for answer choices
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system + system_img},
                        {"role": "user", "content": domain + context + background + request} if img_link == "" else {"role": "user", 
                                                                                                                     "content": [
                                                                                                                         {"type": "text", "text": domain + context + background + request},
                                                                                                                         {
                                                                                                                             "type": "image_url",
                                                                                                                             "image_url": {
                                                                                                                                 "url": img_link
                                                                                                                             }
                                                                                                                         }
                                                                                                                         ]},
                        
                    ]
                )
                
                # wrap in try/except to flag an error if the api fails
                try:
                    # iterate through the output
                    lines = response.choices[0].message.content.split('\n')
                    cur_key = ""
                    num_cor = 0
                    num_incor = 0
                    for line in lines:
                        # check if this line contains a correct answer
                        if line.strip().startswith('C~'):
                            # get the new key
                            num_cor += 1
                            cur_key = "C" + str(num_cor)
                            
                            # set this line into the question dictionary
                            submit_list[cur_key] = line[2:].strip()
                        # check if this line contains a incorrect answer
                        elif line.strip().startswith('I~'):
                            # get the new key
                            num_incor += 1
                            cur_key = "A" + str(num_incor)
                            
                            # set this line into the question dictionary
                            submit_list[cur_key] = line[2:].strip()
                        # otherwise is continuation of previous line
                        else:
                            # if we enter here without a key, something went wrong
                            if cur_key == "":
                                raise Exception()
                            
                            # append this line to the previous on a newline
                            submit_list[cur_key] = "\n" + line.strip()
                except Exception as e:
                    # prompt error and prevent submit
                    messagebox.showerror(":(", "There was an error calling the API, try rewording your question and/or answer choices")
                
                    return
                
            # determine if we need incorrect answer choices
            if "C1" in submit_list.keys() and not "A1" in submit_list.keys():
                # set the environment up
                system = """You are an assistant knowledgeable in many academic subjects. In particular, the user is a student who will specify what domain they request that you fetch knowledge from, while also providing a small paragraph of context that helps you generate helpful responses for the user.

                            In particular, your responses are tailored to generating practice test questions, whether that be filling in missing parts of user-created questions such as picking correct answers, generating incorrect answers, or writing an explanation as to why the correct answer is the correct answer. You will also be providing full-on new practice questions for the user to practice with based on a subset of questions picked and the ascribed domain and context be provided with every input.

                            The input you receive will also be minimal to help with processing and costs associated. You will ALWAYS be given a domain, denoted with the prefix "Domain:" for which the question comes from. In addition, you will ALWAYS be given a subset of "Context:" for which you should prioritize when synthesizing your answer. Lastly, you will receive one of the following:
                            - A question with a single correct answer, followed by a request for incorrect answer choices (provide 3 incorrect answer choices)
                                - Ex. output:
                                    I~ They can only be assigned to variables and stored in data structures
                                    I~ They can only be passed as arguments to other functions
                                    I~ They can only be returned as values from other functions 
                            
                            Since your output will be fed directly to a program to be parsed, you MUST be STRICT with what you output, and be as BRIEF as possible. for ALL outputs, your responses MUST ADHERE TO THE ABOVE FORMAT NO MATTER WHAT
                            
                            Please keep in mind you are free to use any characters in your response as the delimiters will help the program figure out what field means what."""
                
                # get the required context for the prompt
                background = "Question: " + remove_backticked_imbeds(submit_list["Question"]) + "\nCorrect Answer: " + remove_backticked_imbeds(submit_list["C1"]) + "\n"
                request = "Please provide 3 incorrect answer choices given the correct answer"
                
                # prompt for answer choices
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system + system_img},
                        {"role": "user", "content": domain + context + background + request} if img_link == "" else {"role": "user", 
                                                                                                                     "content": [
                                                                                                                         {"type": "text", "text": domain + context + background + request},
                                                                                                                         {
                                                                                                                             "type": "image_url",
                                                                                                                             "image_url": {
                                                                                                                                 "url": img_link
                                                                                                                             }
                                                                                                                         }
                                                                                                                         ]},
                        
                    ]
                )
                
                # wrap in try/except to flag an error if the api fails
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
                            submit_list[cur_key] = line[2:].strip()
                        # otherwise is continuation of previous line
                        else:
                            # if we enter here without a key, something went wrong
                            if cur_key == "":
                                raise Exception()
                            
                            # append this line to the previous on a newline
                            submit_list[cur_key] = "\n" + line.strip()
                except Exception as e:
                    # prompt error and prevent submit
                    messagebox.showerror(":(", "There was an error calling the API, try rewording your question and/or answer choices")
                
                    return
                
            # determine if we need a correct answer choice and some more incorrect answer choices
            if not "C1" in submit_list.keys() and "A1" in submit_list.keys():
                # set the environment up
                system = """You are an assistant knowledgeable in many academic subjects. In particular, the user is a student who will specify what domain they request that you fetch knowledge from, while also providing a small paragraph of context that helps you generate helpful responses for the user.

                            In particular, your responses are tailored to generating practice test questions, whether that be filling in missing parts of user-created questions such as picking correct answers, generating incorrect answers, or writing an explanation as to why the correct answer is the correct answer. You will also be providing full-on new practice questions for the user to practice with based on a subset of questions picked and the ascribed domain and context be provided with every input.

                            The input you receive will also be minimal to help with processing and costs associated. You will ALWAYS be given a domain, denoted with the prefix "Domain:" for which the question comes from. In addition, you will ALWAYS be given a subset of "Context:" for which you should prioritize when synthesizing your answer. Lastly, you will receive one of the following:
                            - A question with 1 incorrect answer choice, followed by a request for a correct answer choice (provide 1 correct answer choice, along with 2 additional incorrect answer choices in that order)
                                - Ex. output:
                                    C~ They can be passed as arguments to other functions, returned as values from other functions, assigned to variables, and stored in data structures
                                    I~ They can only be assigned to variables and stored in data structures
                                    I~ They can only be passed as arguments to other functions
                            
                            Since your output will be fed directly to a program to be parsed, you MUST be STRICT with what you output, and be as BRIEF as possible. for ALL outputs, your responses MUST ADHERE TO THE ABOVE FORMAT NO MATTER WHAT
                            
                            Please keep in mind you are free to use any characters in your response as the delimiters will help the program figure out what field means what."""
                
                # get the required context for the prompt
                background = "Question: " + remove_backticked_imbeds(submit_list["Question"]) + "\nIncorrect Answer: " + remove_backticked_imbeds(submit_list["A1"]) 
                request = "Please provide the correct answer, followed by 2 incorrect answers to the given question, given one of the incorrect answers"
                
                # prompt for answer choices
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system + system_img},
                        {"role": "user", "content": domain + context + background + request} if img_link == "" else {"role": "user", 
                                                                                                                     "content": [
                                                                                                                         {"type": "text", "text": domain + context + background + request},
                                                                                                                         {
                                                                                                                             "type": "image_url",
                                                                                                                             "image_url": {
                                                                                                                                 "url": img_link
                                                                                                                             }
                                                                                                                         }
                                                                                                                         ]},
                        
                    ]
                )
                
                # wrap in try/except to flag an error if the api fails
                try:
                    # iterate through the output
                    lines = response.choices[0].message.content.split('\n')
                    cur_key = ""
                    num_cor = 0
                    num_incor = self.question.answers
                    for line in lines:
                        # check if this line contains a correct answer
                        if line.strip().startswith('C~'):
                            # get the new key
                            num_cor += 1
                            cur_key = "C" + str(num_cor)
                            
                            # set this line into the question dictionary
                            submit_list[cur_key] = line[2:].strip()
                        # check if this line contains a incorrect answer
                        elif line.strip().startswith('I~'):
                            # get the new key
                            num_incor += 1
                            cur_key = "A" + str(num_incor)
                            
                            # set this line into the question dictionary
                            submit_list[cur_key] = line[2:].strip()
                        # otherwise is continuation of previous line
                        else:
                            # if we enter here without a key, something went wrong
                            if cur_key == "":
                                raise Exception()
                            
                            # append this line to the previous on a newline
                            submit_list[cur_key] = "\n" + line.strip()
                except Exception as e:
                    # prompt error and prevent submit
                    messagebox.showerror(":(", "There was an error calling the API, try rewording your question and/or answer choices")
                
                    return
                
            # if no explaination exists for the correct answer to this question, or one has been requested via a flag, generate an explaination
            if submit_list["Explaination"] == "" or self.refresh_explaination_flag:
                # set the environment up
                system = r"""You are an assistant knowledgeable in many academic subjects. In particular, the user is a student who will specify what domain they request that you fetch knowledge from, while also providing a small paragraph of context that helps you generate helpful responses for the user.

                            In particular, your responses are tailored to generating practice test questions, whether that be filling in missing parts of user-created questions such as picking correct answers, generating incorrect answers, or writing an explanation as to why the correct answer is the correct answer. You will also be providing full-on new practice questions for the user to practice with based on a subset of questions picked and the ascribed domain and context be provided with every input.

                            The input you receive will also be minimal to help with processing and costs associated. You will ALWAYS be given a domain, denoted with the prefix "Domain:" for which the question comes from. In addition, you will ALWAYS be given a subset of "Context:" for which you should prioritize when synthesizing your answer. Lastly, you will receive one of the following:
                            - A question followed by its correct answer(s) (provide the explaination for why the correct answer is correct in the context of the question).
                                - Ex. output:
                                    E~ A heap is a data structure used for collections where the maximal or minimal element is frequently accessed from the collection, as it performs this operations in near constant time, so a heap would be the best data structure for implementing A* pathfinding.

                            For your explaination, make sure it is INSIGHTFUL and HELPFUL for the student, DO NOT USE ELEMENTS OF THE QUESTION OR ANSWERS WORD FOR WORD IN YOUR RESPONSE.
                            Since your output will be fed directly to a program to be parsed, you MUST be STRICT with what you output, and be as BRIEF as possible. for ALL outputs, your responses MUST ADHERE TO THE ABOVE FORMAT NO MATTER WHAT
                            
                            Please keep in mind you are free to use any characters in your response as the delimiters will help the program figure out what field means what."""
                
                # get the required context for the prompt
                correct_answers = "Correct Answers: "
                for key, value in submit_list.items():
                    if "C" in key:
                        correct_answers += value + ", "
                background = "Question: " + remove_backticked_imbeds(submit_list['Question']) + "\n" + remove_backticked_imbeds(correct_answers) + "\n"
                request = "Please provide the explaination for why the correct answers are correct in the context of the question"
                
                # prompt for answer choices
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system + system_img},
                        {"role": "user", "content": domain + context + background + request} if img_link == "" else {"role": "user", 
                                                                                                                     "content": [
                                                                                                                         {"type": "text", "text": domain + context + background + request},
                                                                                                                         {
                                                                                                                             "type": "image_url",
                                                                                                                             "image_url": {
                                                                                                                                 "url": img_link
                                                                                                                             }
                                                                                                                         }
                                                                                                                         ]},
                        
                    ]
                )
                
                # wrap in try/except to flag an error if the api fails
                try:
                    # push to explaination
                    submit_list['Explaination'] = response.choices[0].message.content[2:].strip()
                except Exception as e:
                    # prompt error and prevent submit
                    messagebox.showerror(":(", "There was an error calling the API, try rewording your question and/or answer choices")
                
                    return
        
        # check if we are making a new question or pushing information back to a previous index
        if int(submit_list['Q']) <= self.parent.q_count.get():
            # push this content to the preexisting clickable reference that already exists at this index
            self.parent.saved_questions[int(submit_list['Q']) - 1].content = submit_list
            self.parent.saved_questions[int(submit_list['Q']) - 1].update_truncate_amount(None)
            
            # update button
            self.submit_question_button.configure(text="Submit Question")
            self.submit_question_button.configure(fg_color = SECONDARY)
            self.submit_question_button.configure(hover_color = SECONDARY_HOVER)
        else:
            # create a clickable reference in the side menu that contains this information
            self.parent.saved_questions.append(QuestionFrame(self.question_preview_frame, self.parent, self, submit_list))
        
            # inc question count
            self.parent.q_count.set(self.parent.q_count.get() + 1)
            
        # get the next index for the question
        self.q_index = self.parent.q_count.get() + 1
        self.question_index.set('Question ' + str(self.q_index))
        
        # clear entry for question
        self.question.destroy()
        self.question = MultipleChoice(self.question_frame, self.modified)
        self.is_modified = False
        self.reset_explaination_refresh()
        
        # flag being modified in the parent
        self.parent.modified = True
        
    def modified(self, event):
        self.is_modified = True
        
    def push_to_explaination(self, event):
        # resize the explain frame entry field to accomidate to its contents
        force_update_textbox_height(self.explain_frame_entry, 465, self.explain_frame_entry.get('1.0', 'end-1c'))
        
        # push the contents of the explain frame entry field to the explanation field of the question
        self.question.explaination = self.explain_frame_entry.get('1.0', 'end-1c')
        
        # flag modification
        self.is_modified = True
            
class QuestionFrame(ctk.CTkFrame):
    def __init__(self, parent_frame, parent, builder_frame, content):
        super().__init__(parent_frame, fg_color='transparent')
        
        # exterior references
        self.parent = parent
        self.builder_frame = builder_frame
        
        # stored content
        self.content = content
        
        # dyn index
        self.trunc_amt = 10
        self.title = tk.StringVar()
        self.title.set("Q. " + self.content['Q'] + ": " + self.content["Question"][:int(self.trunc_amt)].replace('\n', ' ') + ("..." if len(self.content["Question"]) > self.trunc_amt else ""))
        
        # configure frame
        self.columnconfigure(0, weight=8, uniform='a')
        self.columnconfigure(1, weight=1, uniform='a')
        self.rowconfigure(0, weight=1)
        self.bind('<Configure>', self.update_truncate_amount)
        
        # button to fetch this question into the frame
        self.fetch_button = ctk.CTkButton(self, fg_color=LIGHT, text_color=DARK, textvariable=self.title, font=(FONT, NORMAL_FONT_SIZE, 'bold'), command=self.fetch_question_information)
        self.fetch_button.grid(row=0, column=0, sticky='snew', padx=2, pady=2)
        
        # add an ai generated logo if this content signals that this was ai generated
        if("AI Generated" in self.content):
            ai_enhanced = ctk.CTkImage(Image.open(resource_path("AI Enhanced.png")).resize((96,96)))
            self.fetch_button.configure(image=ai_enhanced)
            
            # delete this key from content when intercepted
            del self.content["AI Generated"]
        
        # add an flag logo if this content signals that this was flagged
        if("Flag" in self.content):
            flagged = ctk.CTkImage(Image.open(resource_path("Flagged for Attention.png")).resize((96,96)))
            self.fetch_button.configure(image=flagged)
            
            # delete this key from content when intercepted
            del self.content["Flag"]
            
        # if missing forced (since it was added after a legacy build), add a default value here
        if not "Forced" in self.content:
            self.content["Forced"] = '0'
        
        # button to delete this question
        self.delete_button = ctk.CTkButton(self, fg_color='transparent', text='X', text_color=LIGHT, hover_color=PRIMARY, font=(FONT, NORMAL_FONT_SIZE, 'bold'), command=self.delete_question)
        self.delete_button.grid(column=1, row=0, sticky='snew')
        
        # pack
        self.pack()
        
    def fetch_question_information(self):
        # first check if the user is sure they want to swap from the current question if it is modified
        if(self.builder_frame.is_modified and messagebox.askyesno("Hold it!", "You changes have not been saved yet! Do you want to save them first?")):
            self.builder_frame.submit_question()
            
            return
        
        # set the current question index appropriately in the builder
        self.builder_frame.q_index = self.content['Q']
        self.builder_frame.question_index.set('Question ' + str(self.builder_frame.q_index))
        
        # update button to reflect that this question is being edited
        self.builder_frame.submit_question_button.configure(text="Update Question")
        self.builder_frame.submit_question_button.configure(fg_color = SUCCESS)
        self.builder_frame.submit_question_button.configure(hover_color = SUCCESS_HOVER)
        
        # clear the entry for the question, and instead create a new question using this content
        self.builder_frame.question.destroy()
        self.builder_frame.question = MultipleChoice(self.builder_frame.question_frame, self.builder_frame.modified, self.content)
        self.builder_frame.enable_explaination_refresh()
        self.builder_frame.is_modified = False
        
    def delete_question(self):
        # first check if the user is sure they want to delete this question
        if(not messagebox.askyesno("Wait one Sec!", "Are you sure you want to delete this question? You cannot undo this action")):
            return
        
        # remove this question from the side list
        self.pack_forget()
        self.parent.saved_questions.remove(self)
        
        # decrement question count in parent
        self.parent.q_count.set(self.parent.q_count.get() - 1)
        
        # set the new indices of the items remaining in the side list
        for i, question_button in enumerate(self.parent.saved_questions):
            question_button.content['Q'] = str(i + 1)
            question_button.update_truncate_amount(None)
        
            
        # check if this question matches the current index
        if int(self.builder_frame.q_index) == int(self.content['Q']):
            # We deleted this question, so remake a new question frame
            self.builder_frame.question.destroy()
            self.builder_frame.question = MultipleChoice(self.builder_frame.question_frame, self.builder_frame.modified)
            self.builder_frame.is_modified = False
            
            # Refresh button
            self.builder_frame.submit_question_button.configure(text="Submit Question")
            self.builder_frame.submit_question_button.configure(fg_color = SECONDARY)
            self.builder_frame.reset_explaination_refresh()
            
            # Set the question index of the new question as if we just submitted a new question
            self.builder_frame.q_index = self.parent.q_count.get() + 1
            self.builder_frame.question_index.set('Question ' + str(self.builder_frame.q_index))
        else:   
            # We might of offset the current question's index if its after what we deleted.
            if(int(self.content['Q']) < int(self.builder_frame.q_index)):
                self.builder_frame.q_index = int(self.builder_frame.q_index) - 1
                
            self.builder_frame.question_index.set('Question ' + str(self.builder_frame.q_index))
        
    def update_truncate_amount(self, event):
        # calculate the new character amount that should be displayed in the question field
        self.trunc_amt = self.winfo_width() / 10 - 7
        self.title.set("Q. " + self.content['Q'] + ": " + self.content["Question"][:int(self.trunc_amt)].replace('\n', ' ') + ("..." if len(self.content["Question"]) > self.trunc_amt else ""))
          
class MultipleChoice(ctk.CTkFrame):
    def __init__(self, parent, modified_func, context = None):
        super().__init__(parent, fg_color='transparent')
        
        # pack at the top of the frame 3 radio buttons allowing for questions to be "forced" to be MC, FRQ, or either
        self.forced = tk.IntVar()
        self.forced.set(0)
        self.forced_to_be = ctk.CTkFrame(self, fg_color='transparent')
        self.frq = ctk.CTkRadioButton(self.forced_to_be, radiobutton_height=9, radiobutton_width=9, text="Force FRQ", variable=self.forced, font=(FONT, SMALL_FONT_SIZE), value=2)
        self.frq.pack(side='right')
        self.mc = ctk.CTkRadioButton(self.forced_to_be, radiobutton_height=9, radiobutton_width=9, text="Force MC", variable=self.forced, font=(FONT, SMALL_FONT_SIZE), value=1)
        self.mc.pack(side='right')
        self.either = ctk.CTkRadioButton(self.forced_to_be, radiobutton_height=9, radiobutton_width=9, text="Either", variable=self.forced, font=(FONT, SMALL_FONT_SIZE), value=0)
        self.either.pack(side='right')
        self.forced_to_be.pack(expand=True, fill='both')
        
        # create a frame for the question entry
        self.question = ctk.CTkFrame(self, fg_color='transparent')
        self.question.columnconfigure(0, weight=3)
        self.question.columnconfigure(1, weight=12)
        self.question.rowconfigure(0,weight=1)
        self.question_label = ctk.CTkLabel(self.question, text="Question: ", fg_color='transparent', font=(FONT, NORMAL_FONT_SIZE))
        self.question_label.grid(row=0, column=0, sticky='nw', pady=10)
        self.question_entry = ctk.CTkTextbox(self.question, font=(FONT, NORMAL_FONT_SIZE), height=20)
        self.question_entry.grid(column=1, row=0, sticky='ew')
        self.question_entry.bind('<KeyRelease>', modified_func)
        self.question.pack(fill='x', side='top', pady=2)
        
        # create a scrollable frame for the multiple choice answers
        self.scroll_answers = ctk.CTkScrollableFrame(self, fg_color='transparent')
        self.scroll_answers.pack(fill='x')
        
        # data
        self.answer_choice_guis = []
        self.gui_held_information = []
        self.explaination = ""
        self.answers = 0
        self.correct_answers = 0
        self.modified_func = modified_func
        
        # create a button for adding a correct answer
        self.answer_choice_guis.append(ctk.CTkButton(self.scroll_answers, fg_color=SUCCESS, hover_color=SUCCESS_HOVER, text_color=BG, text='+', font=(FONT, NORMAL_FONT_SIZE, 'bold'), command=self.add_correct_answer_field))
        self.answer_choice_guis[0].pack(fill='x', side='top', pady=2)
        
        # create a button for adding answer choices
        self.answer_choice_guis.append(ctk.CTkButton(self.scroll_answers, fg_color=PRIMARY, hover_color=PRIMARY_HOVER, text_color=BG, text='+', font=(FONT, NORMAL_FONT_SIZE, 'bold'), command=self.add_answer_field))
        self.answer_choice_guis[1].pack(fill='x', side='top', pady=2)
        
        # freeze frame: are we taking context? and if so we fill our fields with said context first!
        if context != None:
            # get the variable fields from the context, this one is easy
            for key, value in context.items():
                # skip index
                if key == 'Q':
                    continue
                
                # is this key a question key
                if key == 'Question':
                    # create and assign to the question variables
                    self.gui_held_information.append(tk.StringVar()) # Holds the information written in the question entry field
                    self.gui_held_information[0].set(value)
                    
                    # force in text and update
                    self.question_entry.insert(tk.END, value)
                    force_update_textbox_height(self.question_entry, 465, value)
                    
                # is this key a correct answer
                if "C" in key:
                    # add an arbitrary correct answer using button event
                    self.add_correct_answer_field()
                    
                    # force update the data variable associated with this answer
                    self.gui_held_information[self.correct_answers].set(value)
                    self.answer_choice_guis[self.correct_answers - 1].choice_entry.insert(tk.END, value)
                    force_update_textbox_height(self.answer_choice_guis[self.correct_answers - 1].choice_entry, 385, value)
                
                # is this key an answer choice
                if "A" in key:
                    # add an arbitrary correct answer using button event
                    self.add_answer_field()
                    
                    # force update the data variable associated with this answer
                    self.gui_held_information[self.correct_answers + self.answers].set(value)
                    self.answer_choice_guis[self.correct_answers + self.answers].choice_entry.insert(tk.END, value)
                    force_update_textbox_height(self.answer_choice_guis[self.correct_answers + self.answers].choice_entry, 385, value)
                    
                # is this the explaination for the correct answer
                if key == 'Explaination':
                    # assign to the explaintation field
                    self.explaination = value
                    
                # is this the forced state of the question?
                if key == 'Forced':
                    # update the radio button controlled variable
                    self.forced.set(int(value))
                
        else: # new question, empty fields
            self.gui_held_information.append(tk.StringVar()) # Holds the information written in the question entry field
        
        # bind the event to the text box that resizes it on keystrokes
        self.question_entry.bind('<KeyRelease>', lambda x:adjust_textbox_height(x, self.question_entry, 465, self.gui_held_information[0]))
        
        # pack the whole enchilatta
        self.pack(fill='x')
        
    def add_correct_answer_field(self):
        # remove the correct answer button from the current answer count index + 1 and shift it to the next index in the list
        self.answer_choice_guis[self.correct_answers].pack_forget()
        self.answer_choice_guis.insert(self.correct_answers + 1, self.answer_choice_guis[self.correct_answers])
        self.answer_choice_guis[self.correct_answers + 1].pack(fill='x', side='top', pady=2, before=self.answer_choice_guis[self.correct_answers + 2])
        
        # create the new string var that this field will take on
        # we have to check for an incorrect answer, since we no longer have a guarenteed pivot
        if(self.answers == 0):
            self.gui_held_information.append(tk.StringVar())
        else:
            self.gui_held_information.insert(self.correct_answers + 1, tk.StringVar())
        
        # inc. correct answers
        self.correct_answers += 1
        
        # pack the correct answer entry field
        self.answer_choice_guis[self.correct_answers - 1] = CorrectAnswerField(self.scroll_answers, self.correct_answers, self.answer_choice_guis[self.correct_answers], lambda x: self.remove_correct_answer_field(x), self.gui_held_information[self.correct_answers], self.modified_func)
        
    def remove_correct_answer_field(self, index):
        # unpack and remove the current answer choice, reflect in answers
        self.answer_choice_guis[index - 1].pack_forget()
        self.answer_choice_guis.remove(self.answer_choice_guis[index - 1])
        self.gui_held_information.remove(self.gui_held_information[index])
        self.correct_answers -= 1
        
        # update the indices of the answer choices
        for i, ans_field in enumerate(self.answer_choice_guis):
            # pass when above correct answers
            if (i + 1) > self.correct_answers:
                break
            # update the index to the current index in the list
            ans_field.update_index(i + 1)
        
    def add_answer_field(self):
        # remove the incorrect answer button from current answer count index + 1 and shift it to the next index in the list
        self.answer_choice_guis[self.correct_answers + self.answers + 1].pack_forget()
        self.answer_choice_guis.append(self.answer_choice_guis[self.correct_answers + self.answers + 1])
        self.answer_choice_guis[self.correct_answers + self.answers + 2].pack(fill='x', side='top', pady=2)
        
        # create the new string var that this field will take on
        self.gui_held_information.append(tk.StringVar())
        
        # inc answers
        self.answers += 1
        
        # pack the new answer choice
        self.answer_choice_guis[self.correct_answers + self.answers] = AnswerField(self.scroll_answers, self.answers, self.answer_choice_guis[self.correct_answers + self.answers + 1], lambda x: self.remove_answer_field(x), self.gui_held_information[self.correct_answers + self.answers], self.modified_func)
        
    def remove_answer_field(self, index):
        # unpack and remove the current answer choice, reflect in answers
        self.answer_choice_guis[self.correct_answers + index].pack_forget()
        self.answer_choice_guis.remove(self.answer_choice_guis[self.correct_answers + index])
        self.gui_held_information.remove(self.gui_held_information[self.correct_answers + index])
        self.answers -= 1
        
        # update the indices of the answer choices
        for i, ans_field in enumerate(self.answer_choice_guis):
            # pass when at or below correct answers and break when above the sum of answers and correct answers
            if i <= self.correct_answers:
                continue
            elif i > (self.answers + self.correct_answers):
                break
            # update the index to the current index in the list (adjusted from correct answer count)
            ans_field.update_index(i - self.correct_answers)
        
class AnswerField(ctk.CTkFrame):
    def __init__(self, parent, index, prior, remove_func, variable, modified_func):
        super().__init__(parent, fg_color='transparent')
        
        # varible to denote answer choice number
        self.index = index
        self.answer_choice_num = tk.StringVar()
        self.answer_choice_num.set("Ans. C. " + str(index) + ":")
        
        # create the block that contains the answer field
        self.columnconfigure(0, weight=5,uniform='a')
        self.columnconfigure(1, weight=18,uniform='a')
        self.columnconfigure(2, weight=2,uniform='a')
        self.rowconfigure(0,weight=1,uniform='b')
        self.choice_label = ctk.CTkLabel(self, text="Question: ", fg_color='transparent', font=(FONT, NORMAL_FONT_SIZE), textvariable=self.answer_choice_num)
        self.choice_label.grid(row=0, column=0, sticky='nw', pady=5)
        self.choice_entry = ctk.CTkTextbox(self, font=(FONT, NORMAL_FONT_SIZE), height=20)
        self.choice_entry.grid(column=1, row=0, sticky='ew', padx=10)
        self.choice_entry.bind('<KeyRelease>', lambda x:adjust_textbox_height(x, self.choice_entry, 385, variable))
        self.choice_entry.bind('<KeyRelease>', modified_func)
        self.delete_button = ctk.CTkButton(self, fg_color='transparent', text='X', text_color=DARK, hover_color=PRIMARY, font=(FONT, NORMAL_FONT_SIZE, 'bold'), command=lambda:remove_func(self.index))
        self.delete_button.grid(column=2, row=0, sticky='snew')
        self.pack(fill='x', side='top', pady=2, before=prior)
        
    def update_index(self, index):
        # update the variables associated with knowing this answer choice's index
        self.index = index
        self.answer_choice_num.set("Ans. C. " + str(index) + ":")
        
class CorrectAnswerField(AnswerField):
    def __init__(self, parent, index, prior, remove_func, variable, modified_func):
        super().__init__(parent, index, prior, remove_func, variable, modified_func)
        
        # update variable to specify that this is the correct answer
        self.answer_choice_num.set("Cor. Ans. " + str(index) + ":")
        
    def update_index(self, index):
        # update the variables associated with knowing this answer choice's index
        self.index = index
        self.answer_choice_num.set("Cor. Ans. " + str(index) + ":")
