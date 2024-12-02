import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
from options import *
from builder import *
from quiz import *
import os
import json
from QAPI import *

# RegeX patterns
patterns = {
    'Name': r'Name:\s*([\s\S]+?)(?=\n\w+:|$)',
    'Domain': r'Domain:\s*([\s\S]+?)(?=\n\w+:|$)',
    'Context': r'Context:\s*([\s\S]+?)(?=-=-=-=-)'
}

class Quizzy(ctk.CTk):
    def __init__(self):
        # set the theme
        super().__init__(fg_color=BG)
        self.title('Quizzy')
        self.geometry('1000x925')
        self.iconbitmap(resource_path('Quizzy_Icon.ico'))
        self.resizable(True, True)
        self.minsize(1000, 925)
        
        # map closing with the x button
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # start with the main menu frame, pass in the function that calls the builder frame
        self.current_frame = MainMenu(self, lambda x,y,z,w:self.get_builder(x, y, z, w))
        
        # main loop
        self.mainloop()
        
    def on_close(self):
        print("Cleaning up")
        self.destroy()
        
    def get_builder(self, data, content, settings, modified):
        # change the title dynamically
        self.title('Quizzy - Making Quiz on: ' + data.get('Domain', "Any Domain"))
        
        # map closing with the x button
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # clear out the old frame, get the builder frame
        self.current_frame.pack_forget()
        self.current_frame.destroy()
        self.current_frame = Builder(self, data, self.get_mainmenu, content, lambda x, y, z, w: self.get_quiz(x, y, z, w), modified, settings)
        
    def get_mainmenu(self):
        # change the title dynamically
        self.title('Quizzy')
        
        # clear out the old frame, get the main menu frame
        self.current_frame.pack_forget()
        self.current_frame.destroy()
        self.current_frame = MainMenu(self, lambda x,y,z,w:self.get_builder(x, y, z, w))
        
    def get_quiz(self, data, content, quiz_properties, settings):
        # change the title dynamically
        self.title('Quizzy - Taking Quiz on ' + data[0])
        
        # disable close button
        self.protocol("WM_DELETE_WINDOW", lambda: None)
        
        # clear out the old frame, get the quiz frame
        self.current_frame.pack_forget()
        self.current_frame.destroy()
        self.current_frame = Quiz(self, data, content, quiz_properties["question_count"], quiz_properties["ai_settings"], quiz_properties["frq_prop"], quiz_properties["questions_per_page"], quiz_properties["time_limit"], lambda x,y,z,w:self.get_builder(x, y, z, w), quiz_properties["was_modified"], settings, quiz_properties["ai_questions_are_added"])
        
class MainMenu(ctk.CTkFrame):
    def __init__(self, parent, get_builder):
        super().__init__(parent, fg_color='transparent')
        
        # exterior function and data
        self.get_builder = get_builder
        self.question_data = []
        self.file_path = ""
        
        # Create a frame for the main application interface
        self.menu_frame = ctk.CTkFrame(self, fg_color=LIGHT, corner_radius=20)
        self.menu_frame.pack(pady=10, ipady=10, ipadx=30, anchor='center')
        
        # Create the main application interface
        self.app_title = ctk.CTkLabel(self.menu_frame, text='Quizzy', font=(FONT, HEADER_FONT_SIZE, 'bold'))
        self.app_title.pack(pady=10)
        self.explaination = ctk.CTkLabel(self.menu_frame, text='By: Xander Corcoran (IXtimes)', font=(FONT, NORMAL_FONT_SIZE))
        self.explaination.pack(pady=2.5)
        self.explaination = ctk.CTkLabel(self.menu_frame, text='To get started, try providing some context for the quiz that you will be designing:', font=(FONT, NORMAL_FONT_SIZE))
        self.explaination.pack(pady=2.5)
        
        # domain entry
        self.domain = ctk.CTkFrame(self.menu_frame, fg_color='transparent')
        self.domain.columnconfigure(0, weight=3)
        self.domain.columnconfigure(1, weight=12)
        self.domain.rowconfigure(0,weight=1)
        self.domain_label = ctk.CTkLabel(self.domain, text="Domain: ", fg_color='transparent', font=(FONT, NORMAL_FONT_SIZE))
        self.domain_label.grid(row=0, column=0, sticky='nw', pady=5, ipadx=5)
        self.domain_entry = ctk.CTkTextbox(self.domain, text_color=SELECT_BG, font=(FONT, NORMAL_FONT_SIZE), height=20)
        self.domain_entry.grid(column=1, row=0, sticky='ew')
        self.domain.pack(fill='x', side='top', pady=2, padx=25)
        
        # context entry
        self.context = ctk.CTkFrame(self.menu_frame, fg_color='transparent')
        self.context.columnconfigure(0, weight=3)
        self.context.columnconfigure(1, weight=12)
        self.context.rowconfigure((0, 1),weight=1)
        self.context_label = ctk.CTkLabel(self.context, text="Context: ", fg_color='transparent', font=(FONT, NORMAL_FONT_SIZE))
        self.context_label.grid(row=0, column=0, sticky='nw', pady=5, ipadx=5)
        context_from_file_image = Image.open(resource_path("Add File.png")).resize((32,32))
        self.context_import_from_file = ctk.CTkButton(self.context, image=ctk.CTkImage(context_from_file_image), fg_color=SECONDARY, hover_color=SECONDARY_HOVER, text='', font=(FONT, NORMAL_FONT_SIZE), height=32, width=32, command=self.append_to_context_from_file)
        self.context_import_from_file.grid(row=1, column=0, padx=10, sticky='es')
        self.context_entry = ctk.CTkTextbox(self.context, text_color=SELECT_BG, font=(FONT, NORMAL_FONT_SIZE), height=160)
        self.context_entry.grid(column=1, row=0, rowspan=2, sticky='ew')
        self.context.pack(fill='x', side='top', pady=2, padx=25)
        
        # Bind the functions to the appropriate events
        self.domain_hint_text = "Enter the subject domain that this quiz covers..."
        self.context_hint_text = "Add additional notes, textbook passages, or lecture slide\ncontents to reference before referring an internal\ngeneral database..."
        self.domain_entry.insert(tk.END, self.domain_hint_text)
        self.context_entry.insert(tk.END, self.context_hint_text)
        self.domain_entry.bind("<FocusIn>", lambda x:self.clear_hint(x, self.domain_entry))
        self.domain_entry.bind("<FocusOut>", lambda x:self.insert_hint(x, self.domain_entry, True))
        self.context_entry.bind("<FocusIn>", lambda x:self.clear_hint(x, self.context_entry))
        self.context_entry.bind("<FocusOut>", lambda x:self.insert_hint(x, self.context_entry, False))
        
        # Create the remaining application interface
        self.new_quiz_button = ctk.CTkButton(self.menu_frame, fg_color=INFO, hover_color=INFO_HOVER, text='Create new quiz', font=(FONT, NORMAL_FONT_SIZE), height=28, command=self.open_quiz)
        self.new_quiz_button.pack(fill='x', expand=True, padx=10, pady=2.5)
        self.import_quiz_text = ctk.CTkLabel(self.menu_frame, text='Or continue working with a previous quiz:', font=(FONT, NORMAL_FONT_SIZE))
        self.import_quiz_text.pack(pady=2.5)
        self.import_quiz_button = ctk.CTkButton(self.menu_frame, fg_color=SECONDARY, hover_color=SECONDARY_HOVER, text='Import preexisting quiz', font=(FONT, NORMAL_FONT_SIZE), height=28, command=self.import_quiz_information)
        self.import_quiz_button.pack(fill='x', expand=True, padx=10, pady=2.5)
        
        # Create a frame for the main application settings
        self.settings_frame = ctk.CTkFrame(self, fg_color=LIGHT, corner_radius=20)
        self.settings_frame.pack(pady=10, ipady=10, anchor='center')
        
        # Create the settings interface
        self.settings_title = ctk.CTkLabel(self.settings_frame, text='Settings', font=(FONT, TITLE_FONT_SIZE, 'bold'))
        self.settings_title.pack(pady=10)
        self.settings_expl = ctk.CTkLabel(self.settings_frame, text='Configure Quizzy\'s features here:', font=(FONT, NORMAL_FONT_SIZE))
        self.settings_expl.pack(pady=2.5)
        self.settings_region = ctk.CTkFrame(self.settings_frame, fg_color='transparent')
        self.settings_region.columnconfigure(0,weight=2)
        self.settings_region.columnconfigure(1,weight=3)
        self.settings_region.columnconfigure(2,weight=1)
        self.settings_region.rowconfigure((0,1,2,3,4),weight=1)
        self.settings_region.pack(pady=2.5, padx=10)
        
        # API key entry
        self.apikey_label = ctk.CTkLabel(self.settings_region, text="OpenAI API Key:", fg_color='transparent', font=(FONT, NORMAL_FONT_SIZE))
        self.apikey_label.grid(row=0, column=0, sticky='en', padx=10, pady=3)
        image = Image.open(resource_path("Enhanced.png")).resize((22,22))
        self.show_apikey = ctk.CTkButton(self.settings_region, image=ctk.CTkImage(image), fg_color=DANGER, hover_color=DANGER_HOVER, text='Show API Key', font=(FONT, NORMAL_FONT_SIZE), height=28, width=400, command=self.show_api_key)
        self.show_apikey.grid(row=0, column=1, sticky='snew', padx=25, pady=2, columnspan=2)
        self.apikey_frame_amnt = ctk.CTkTextbox(self.settings_region, font=(FONT, NORMAL_FONT_SIZE), height=20, width=400)
        
        # Model selection
        self.model_index_var = tk.IntVar()
        self.model_index_var.set(0)
        self.model_to_be = ctk.CTkFrame(self.settings_region, fg_color='transparent')
        self.model_label = ctk.CTkLabel(self.settings_region, text="Model:", fg_color='transparent', font=(FONT, NORMAL_FONT_SIZE))
        self.model_label.grid(row=1, column=0, sticky='ne', padx=25, pady=2)
        self.GPT_model_2_radio_input = ctk.CTkRadioButton(self.model_to_be, radiobutton_height=12, radiobutton_width=12, text="GPT-o1 (Math/Sci, expensive)", variable=self.model_index_var, font=(FONT, NORMAL_FONT_SIZE), value=2)
        self.GPT_model_2_radio_input.pack(side='right', padx=20)
        self.GPT_model_1_radio_input = ctk.CTkRadioButton(self.model_to_be, radiobutton_height=12, radiobutton_width=12, text="GPT-4o (Lang/Hist, costly)", variable=self.model_index_var, font=(FONT, NORMAL_FONT_SIZE), value=1)
        self.GPT_model_1_radio_input.pack(side='right', padx=20)
        self.GPT_model_0_radio_input = ctk.CTkRadioButton(self.model_to_be, radiobutton_height=12, radiobutton_width=12, text="GPT-4o mini (General, cheap)", variable=self.model_index_var, font=(FONT, NORMAL_FONT_SIZE), value=0)
        self.GPT_model_0_radio_input.pack(side='right', padx=20)
        self.model_to_be.grid(row=1, column=1, sticky='nw', padx=25, pady=2, columnspan=2)
        
        # Offline mode
        self.is_offline_var = tk.IntVar()
        self.is_offline_var.set(0)
        self.is_offline_to_be = ctk.CTkFrame(self.settings_region, fg_color='transparent')
        self.is_offline_label = ctk.CTkLabel(self.settings_region, text="Enable offline mode?", fg_color='transparent', font=(FONT, NORMAL_FONT_SIZE))
        self.is_offline_label.grid(row=2, column=0, sticky='ne', padx=25, pady=2)
        self.is_offline = ctk.CTkRadioButton(self.is_offline_to_be, radiobutton_height=12, radiobutton_width=12, text="Yes (Disables online features)", variable=self.is_offline_var, font=(FONT, NORMAL_FONT_SIZE), value=1)
        self.is_offline.pack(side='right', padx=40)
        self.is_online = ctk.CTkRadioButton(self.is_offline_to_be, radiobutton_height=12, radiobutton_width=12, text="No", variable=self.is_offline_var, font=(FONT, NORMAL_FONT_SIZE), value=0)
        self.is_online.pack(side='right', padx=40)
        self.is_offline_to_be.grid(row=2, column=1, sticky='nw', padx=25, pady=2, columnspan=2)
        
        # Context cutoff entry
        #self.context_cutoff_label = ctk.CTkLabel(self.settings_region, text="Context cutoff:", fg_color='transparent', font=(FONT, NORMAL_FONT_SIZE))
        #self.context_cutoff_label.grid(row=3, column=0, sticky='ne', padx=25, pady=2)
        #self.context_cutoff_amnt = ctk.CTkTextbox(self.settings_region, font=(FONT, NORMAL_FONT_SIZE), height=20)
        #self.context_cutoff_amnt.grid(row=3, column=1, sticky='snew', padx=25, pady=2, columnspan=2)
        
        # slider for batch size
        #self.batch_size = tk.IntVar()
        #self.batch_size.set(5)
        #self.batch_size_label = ctk.CTkLabel(self.settings_region, text="Batch size: ", fg_color='transparent', font=(FONT, NORMAL_FONT_SIZE))
        #self.batch_size_label.grid(row=4, column=0, sticky='ne', padx=25, pady=2)
        #self.batch_size_amount_label = ctk.CTkLabel(self.settings_region, textvariable=self.batch_size, fg_color='transparent', font=(FONT, NORMAL_FONT_SIZE))
        #self.batch_size_amount_label.grid(row=4, column=2, sticky='nw', padx=25, pady=2)
        #self.batch_size_slider = ctk.CTkSlider(self.settings_region, from_=1, to=5, variable=self.batch_size)
        #self.batch_size_slider.grid(row=4, column=1, sticky='ew', padx=25, pady=2)
        
        # Once the entire UI has loaded in, fetch the settings and write them to the settings fields
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
                self.apikey_frame_amnt.insert(tk.END, settings['API Key'])
                self.model_index_var.set(settings['Model'])
                self.is_offline_var.set(1 if settings['Offline'] else 0)
                #self.context_cutoff_amnt.insert(tk.END, str(settings['ContextCut']))
                #self.batch_size.set(settings['Batch'])
            except Exception as e:
                # write from dictionary to fields
                self.apikey_frame_amnt.insert(tk.END, settings['API Key'])
                self.model_index_var.set(1)
                self.is_offline_var.set(0)
                #self.context_cutoff_amnt.insert(tk.END, "0")
                #self.batch_size.set(5)
        
        # pack the main menu
        self.pack(expand=True, fill='both', anchor='center')
     
    def append_to_context_from_file(self):
        # get the text content from a more complex file and simply append that to the context segment
        files_to_get_context_from = filedialog.askopenfilenames(defaultextension='*.txt *.docx *.pdf *.pptx', filetypes=[("ALL Supported Types", "*.txt *.docx *.pdf *.pptx"), ("Text", "*.txt"), ("Word Document", "*.docx"), ("PDF Document", "*.pdf"), ("Powerpoint Presentation", "*.pptx")])
        
        # get the collated text content from all those files
        text_content = get_text_context_from_file(files_to_get_context_from)
        
        # append it to the current context and display it in the appropriate text fields
        if files_to_get_context_from:
            self.clear_hint(None, self.context_entry)
            self.context_entry.insert(tk.END, text_content)
        
    def show_api_key(self):
        # hide the show api key button
        self.show_apikey.grid_forget()
        
        # show the api key entry field
        self.apikey_frame_amnt.grid(row=0, column=1, sticky='snew', padx=25, pady=2)
        
    def import_quiz_information(self):
        self.domain, self.context, self.question_data, self.file_path = import_from_quizzy_file()
        
        # check if we got information from a file correctly
        if self.question_data:
            # package what was read into the entries in the main menu
            self.domain_entry.delete(1.0, tk.END)
            self.domain_entry.insert(tk.END, self.domain)
            self.domain_entry.configure(text_color=DARK)
            self.context_entry.delete(1.0, tk.END)
            self.context_entry.insert(tk.END, self.context)
            self.context_entry.configure(text_color=DARK)
            
            # update create button to reflect an import rather than creating a new quiz
            self.new_quiz_button.configure(fg_color=SUCCESS)
            self.new_quiz_button.configure(hover_color=SUCCESS_HOVER)
            self.new_quiz_button.configure(text="Open this quiz")
        else:
            # clear import fields
            self.domain_entry.delete(1.0, tk.END)
            self.domain_entry.insert(tk.END, self.domain_hint_text)
            self.domain_entry.configure(text_color=SELECT_BG)
            self.context_entry.delete(1.0, tk.END)
            self.context_entry.insert(tk.END, self.context_hint_text)
            self.context_entry.configure(text_color=SELECT_BG)
        
    def open_quiz(self):
        # check if the contents of the domain or context fields are empty
        if self.domain_entry.get('1.0', 'end-1c') == self.domain_hint_text or self.context_entry.get('1.0', 'end-1c') == self.context_hint_text or not self.domain_entry.get('1.0', 'end-1c') or not self.context_entry.get('1.0', 'end-1c'):
            if(not messagebox.askyesno("Notice", "Are you sure you want to enter this quiz without context and/or a domain? While not required these greatly help with generating new practice questions!")):
                return
        
        # test api key
        valid_key = test_api_key(self.apikey_frame_amnt.get('1.0', 'end-1c'))
        
        if not valid_key:
            if messagebox.askyesno("Warning", "It appears the API key that you entered is invalid, would you like to reenter a new key? Otherwise you will continue in offline mode."):
                return
            else:
                self.is_offline_var.set(1)
        
        # check if cutoff amount is set correctly
        #if not self.context_cutoff_amnt.get('1.0', 'end-1c').isdigit() and messagebox.askyesno("Settings check!", "The context cutoff you provided isnt a valid number. Do you want to change it? otherwise it default to 50!"):
        #    return
            
        settings = {'API Key': self.apikey_frame_amnt.get('1.0', 'end-1c'),
                    'Model': self.model_index_var.get(),
                    'Offline': self.is_offline_var.get() != 0}
                    #'ContextCut': self.context_cutoff_amnt.get('1.0', 'end-1c') if self.context_cutoff_amnt.get('1.0', 'end-1c').isdigit() else 50,
                    #'Batch': self.batch_size.get()}  
        
        # push settings information to the user path
        json_settings = json.dumps(settings, indent=4)
        user_path = os.path.expanduser("~")
        directory = os.path.join(user_path, "IXSettings", "Quizzy")
        os.makedirs(directory, exist_ok=True)
        full_path = os.path.join(directory, "quizzy.json")
        with open(full_path, 'w') as file:
            file.write(json_settings)
        
        # create a datem object containing the domain and context for this quiz
        quiz_data = {}
        
        # get the contents of the domain and context fields if they are not their hint texts
        if not self.domain_entry.get('1.0', 'end-1c') == self.domain_hint_text and self.domain_entry.get('1.0', 'end-1c').strip() != "":
            quiz_data['Domain'] = self.domain_entry.get('1.0', 'end-1c')
        else:
            quiz_data['Domain'] = "Any Domain"
        if not self.context_entry.get('1.0', 'end-1c') == self.context_hint_text and self.context_entry.get('1.0', 'end-1c').strip() != "":
            quiz_data['Context'] = self.context_entry.get('1.0', 'end-1c')
        else:
            quiz_data['Context'] = "No Context Provided"
        if self.file_path != "":
            quiz_data['File Path'] = self.file_path
            
        # call in the builder frame to take on this data
        self.get_builder(quiz_data, self.question_data, settings, False)
        
    # Function to clear the hint text when the textbox gains focus
    def clear_hint(self, event, entry):
        if entry.get('1.0', 'end-1c') == self.domain_hint_text:
            entry.configure(text_color=DARK)
            entry.delete(1.0, tk.END)
        if entry.get('1.0', 'end-1c') == self.context_hint_text:
            entry.configure(text_color=DARK)
            entry.delete(1.0, tk.END)
    
    # Function to insert the hint text when the textbox loses focus and is empty
    def insert_hint(self, event, entry, domain):
        if not entry.get('1.0', 'end-1c') and domain:
            entry.configure(text_color=SELECT_BG)
            entry.insert(tk.END, self.domain_hint_text)
        elif not entry.get('1.0', 'end-1c'):
            entry.configure(text_color=SELECT_BG)
            entry.insert(tk.END, self.context_hint_text)
        
if __name__ == '__main__':
    Quizzy()
    
    os._exit(0)