AI Code Optimizer

An intelligent desktop application that analyzes, fixes, and optimizes source code using a combination of rule-based techniques and machine learning. The tool provides real-time error detection, automatic correction, and multiple compiler-level optimizations through an interactive GUI built with Tkinter.

Features
Language Detection
Automatically detects C, C++, Java, and Python code.
Error Detection
Identifies common syntax and logical issues such as:
Missing semicolons
Type mismatches
Incorrect loop syntax
Missing colons in Python control statements
Auto Fix
Applies automatic corrections to detected issues:
Fixes variable assignments
Corrects loop headers
Adds missing syntax elements
Code Optimization
Implements classical compiler optimization techniques:
Constant Folding
Constant Propagation
Algebraic Simplification
Copy Propagation
Dead Code Elimination
Common Subexpression Elimination
Machine Learning Integration
Uses a Naive Bayes model (from scikit-learn) to predict suitable optimization strategies.
Syntax Highlighting
Highlights:
Keywords
Strings
Numbers
Comments
Real-Time Error Feedback
Updates errors dynamically while typing.
PDF Code Input
Extracts code from PDF files using pypdf or PyPDF2.
Voice Input
Converts speech into code input using SpeechRecognition.
Optimization Score
Quantifies improvement based on code reduction.
Theme Support
Toggle between dark and light modes.
Tech Stack
Frontend / GUI
Tkinter (Python standard GUI library)
Backend Logic
Python
Machine Learning
Naive Bayes (via scikit-learn)
Libraries Used
tkinter
re (regular expressions)
operator
threading
scikit-learn
pypdf / PyPDF2
speech_recognition
Installation
Clone the repository:
git clone https://github.com/your-username/ai-code-optimizer.git
cd ai-code-optimizer
Install dependencies:
pip install scikit-learn pypdf SpeechRecognition
Run the application:
python main.py
Usage
Launch the application.
Paste or type your code into the input editor.
Use the available options:
Optimize: Analyze and improve code
PDF: Load code from a PDF file
Voice: Input code via microphone
Copy: Copy optimized output
Save: Export results to a file
Clear: Reset input and output
Theme: Toggle appearance
View:
Fixed code
Optimized code
Optimization steps applied
Error reports
Optimization score
Project Structure
ai-code-optimizer/
│
├── main.py            # Main application file
├── README.md         # Project documentation
└── requirements.txt  # Dependencies (optional)
How It Works
Input Processing
Code is read from the editor, PDF, or voice input.
Language Detection
Pattern-based detection determines the programming language.
Error Analysis
Regular expressions identify syntax and semantic issues.
Auto Fixing
Corrections are applied line by line.
Optimization Pipeline
Code passes through multiple transformation stages:
Constant propagation
Simplification
Folding
Copy optimization
Dead code removal
Subexpression elimination
Machine Learning Suggestion
The trained model predicts the most relevant optimization.
Output Generation
Displays optimized code and performance score.
Limitations
Supports only basic syntax patterns for error detection.
Machine learning model is trained on a small dataset.
Complex multi-file or project-level optimization is not supported.
PDF extraction depends on text-based PDFs (not scanned images).
Future Improvements
Expand ML dataset for better predictions
Add support for more programming languages
Integrate AST-based parsing for deeper analysis
Enable web-based version using frameworks like React and FastAPI
Add code complexity metrics and performance profiling
License

This project is open-source and available under the MIT License.
