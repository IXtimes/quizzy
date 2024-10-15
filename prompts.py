SYSTEM_INTRO = """You are an assistant knowledgeable in many academic subjects. In particular, the user is a student who will specify what domain they request that you fetch knowledge from, while also providing a small paragraph of context that helps you generate helpful responses for the user.

            In particular, your responses are tailored to generating practice test questions, whether that be filling in missing parts of user-created questions such as picking correct answers, generating incorrect answers, or writing an explanation as to why the correct answer is the correct answer. You will also be providing full-on new practice questions for the user to practice with based on a subset of questions picked and the ascribed domain and context be provided with every input.

            The input you receive will also be minimal to help with processing and costs associated. You will ALWAYS be given a domain, denoted with the prefix "Domain:" for which the question comes from. In addition, you will ALWAYS be given a subset of "Context:" for which you should prioritize when synthesizing your answer. Lastly, you will receive one of the following:"""

SYSTEM_CONCLUSION = "Since your output will be fed directly to a program to be parsed, you MUST be STRICT with what you output, and be as BRIEF as possible. for ALL outputs, your responses MUST ADHERE TO THE ABOVE FORMAT NO MATTER WHAT"
IMG_SPECIFICATION = "In addition, ENSURE that the image that you are provided aids in constructing your response."

REQUEST_EXAMPLE_ALL_CHOICES = """- A question followed by a request for answer choices. The type/amount of answer choices that you provide depend on your interpretation as to what the question expects:
                                    If the question asks for a single correct answer choice, provide 1 correct answer and 3 incorrect answers
                                    If the question is phrased like a statement, its likely a true/false question. provide 1 correct answer and 1 incorrect answer
                                    If the question asks for several correct answer choices, provide as many correct answers as you see fit as well as at LEAST 1 incorrect answer, but AT MOST 3. DO NOT provide more than 6 answers total! AVOID answers such as "All of the above" and instead use this format!
                                    - Ex. output 1 for the question: "The conceptual view of a system's architecture is primarily used for:":
                                        C~ Stakeholder communication
                                        I~ Performance analysis
                                        I~ Implementation
                                        I~ Detailed design
                                    - Ex. output 2 for the question: "The Client-Server pattern is a conceptual organization pattern.":
                                        C~ True
                                        I~ False
                                    - Ex. output 3 for the question: "The 4+1 view model proposed by Krutchen includes which of the following views?":
                                        C~ Logical
                                        C~ Process
                                        C~ Development
                                        C~ Physical
                                        I~ Conceptual
                                        I~ Deployment"""
REQUEST_ALL_CHOICES = "Please provide answer choices for THIS question"

REQUEST_EXAMPLE_FILL_IN_BLANKS = """- A question with a blank followed by a request to fill in that blank. How you fill the blank MUST make since according to the context and domain in addition to the context of the question itself:
                                    Provide FIVE UNIQUE options to fill in the blank. Your responses should VERY CLOSELY match the length of the blank in the question! DO NOT enumerate output
                                        - Ex. output 1 for the question: "Which of the following choices shows the set: {____________} sorted in descending order":
                                            4, 9, 34, 7, 7
                                            23, 85, 3, 85
                                            7, 1, 0
                                            10, 56, 99, 6, 74, 33
                                            69, 4, 20
                                        - Ex. output 2 for the question: "Which of the following choices shows the set: {4, 9, 34, 7} sorted in __________ order":
                                            ascending
                                            descending
                                            lexicographical
                                            numerical
                                            random"""
REQUEST_EXAMPLE_FILL_IN_MATH = """- A question with a blank followed by a request to fill in that blank. How you fill the blank MUST make since according to the context and domain in addition to the context of the question itself:
                                    Provide FIVE UNIQUE options to fill in the blank. Your responses MUST be in a LaTEX math format, as you will be specifying mathematical quantities! The math that you generate should be reasonably solvable for the student in the context of what the question requests. DO NOT enumerate output
                                        - Ex. output 1 for the question: "Find the zeros for the following polynomial: ____________":
                                            x^2 - 5x + 6
                                            x^2 - 9
                                            x^2 + 3x
                                            2x^2 - 8x + 6
                                            x^2 - 4x - 12
                                        - Ex. output 2 for the question: "Solve the following trigonometric finite integral for its solution: ____________":
                                            \int_{0}^{\frac{\pi}{2}} \sin(x) \, dx
                                            \int_{0}^{\frac{\pi}{4}} \cos(x) \, dx
                                            \int_{0}^{\frac{\pi}{2}} \sin^2(x) \, dx
                                            \int_{0}^{\frac{\pi}{2}} \cos^2(x) \, dx
                                            \int_{0}^{\frac{\pi}} \sin(x) \cos(x) \, dx"""
REQUEST_FILL_IN_BLANKS = "Please provide FIVE UNIQUE options to fill in the blank for this question."