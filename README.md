# AI Code Optimizer

An intelligent desktop application that analyzes, fixes, and optimizes source code using rule-based techniques and machine learning. It provides real-time error detection, automatic correction, and multiple compiler-level optimizations through a Tkinter GUI.

---

## Features

### Language Detection
- Supports C, C++, Java, and Python

### Error Detection
- Detects:
  - Missing semicolons
  - Type mismatches
  - Invalid loops
  - Missing colons (Python)

### Auto Fix
- Automatically:
  - Fixes assignments
  - Repairs loops
  - Adds missing syntax

### Code Optimization
- Constant Folding
- Constant Propagation
- Algebraic Simplification
- Copy Propagation
- Dead Code Elimination
- Common Subexpression Elimination

### Machine Learning
- Uses Naive Bayes (scikit-learn) for optimization suggestions

### Other Features
- Syntax highlighting
- Real-time error checking
- PDF code input
- Voice input
- Optimization score
- Dark/light theme toggle

---

## Tech Stack

- Python
- Tkinter (GUI)
- scikit-learn (ML)

---

## Installation

### 1. Clone the repository
```bash
git clone https://github.com/your-username/ai-code-optimizer.git
cd ai-code-optimizer
'''
2. Install dependencies
pip install -r requirements.txt
3. Run the application
python main.py
Usage
Open the app
Paste or type code
Click OPTIMIZE
View:
Fixed code
Optimized code
Errors
Optimization steps
Score
Project Structure
ai-code-optimizer/
├── main.py
├── README.md
└── requirements.txt
Limitations
Works on basic syntax patterns
Small ML dataset
No multi-file support
PDF must contain extractable text
Future Improvements
More languages
Better ML model
AST-based analysis
Web version
License

MIT License


---

This one will render perfectly on GitHub.  
If you still see weird formatting, it means your repo file has leftover characters — just replace the entire README with this.
