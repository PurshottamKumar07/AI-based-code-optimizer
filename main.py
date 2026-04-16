import tkinter as tk
from tkinter import scrolledtext, filedialog, messagebox
import re
import operator
import threading

# ML
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.naive_bayes import MultinomialNB

try:
    import speech_recognition as sr
    SR_AVAILABLE = True
except ImportError:
    SR_AVAILABLE = False

# PDF
try:
    from pypdf import PdfReader
    PDF_AVAILABLE = True
except ImportError:
    try:
        from PyPDF2 import PdfReader
        PDF_AVAILABLE = True
    except ImportError:
        PDF_AVAILABLE = False

# =============================
# ML TRAINING
# =============================
data = [
    ("x = 2 + 3", "Constant Folding"),
    ("a = b + c\nd = b + c", "Common Subexpression"),
    ("x = 10\nx = 20", "Dead Code"),
    ("y = x * 1", "Algebraic Simplification"),
    ("z = x + 0", "Algebraic Simplification"),
    ("a = 5\nb = a", "Constant Propagation"),
    ("c = b\nd = c", "Copy Propagation"),
]

X_train = [d[0] for d in data]
y_train = [d[1] for d in data]

vectorizer = CountVectorizer()
X_vec = vectorizer.fit_transform(X_train)
model = MultinomialNB()
model.fit(X_vec, y_train)

# =============================
# SAFE EVAL (no eval() usage)
# =============================
OPS = {
    '+': operator.add,
    '-': operator.sub,
    '*': operator.mul,
    '/': operator.floordiv,
}

def safe_eval(a, op, b):
    try:
        result = OPS[op](int(a), int(b))
        return str(result)
    except (KeyError, ZeroDivisionError, ValueError):
        return f"{a}{op}{b}"

# =============================
# LANGUAGE DETECTION
# =============================
def detect_language(code):
    if "public class" in code or "System.out" in code:
        return "Java"
    if "#include<iostream>" in code or "#include <iostream>" in code or "cout <<" in code:
        return "C++"
    if "#include<stdio.h>" in code or "#include <stdio.h>" in code or "printf(" in code:
        return "C"
    if "def " in code or "import " in code or "print(" in code:
        return "Python"
    return "Unknown"

# =============================
# ERROR DETECTION
# =============================
def detect_errors(code):
    errors = []
    lines = code.split("\n")
    lang = detect_language(code)

    for i, line in enumerate(lines):
        l = line.strip()
        if not l:
            continue

        if lang == "C":
            if l.startswith("#include") and l.endswith(";"):
                errors.append(f"Line {i+1}: Remove semicolon from #include directive")
            if re.search(r'int\s+\w+\s*=\s*".*"', l):
                errors.append(f"Line {i+1}: Type mismatch — assigning string to int")
            match = re.search(r'char\s+(\w+)\s*=\s*([A-Za-z_]\w*)\s*;?$', l)
            if match:
                errors.append(f"Line {i+1}: Missing single quotes for char '{match.group(1)}'")
            is_control = re.match(r'^(for|while|if)\s*\(', l)
            if l and not l.endswith((";", "{", "}")) and not l.startswith("#") and not l.endswith(":") and not is_control:
                errors.append(f"Line {i+1}: Missing semicolon")
            if "for(" in l and l.count(";") < 2:
                errors.append(f"Line {i+1}: Invalid for loop — missing semicolons in header")

        elif lang == "C++":
            match = re.search(r'string\s+(\w+)\s*=\s*([A-Za-z_]\w*)\s*;?$', l)
            if match:
                errors.append(f"Line {i+1}: Missing quotes for string '{match.group(1)}'")
            if re.search(r'int\s+\w+\s*=\s*".*"', l):
                errors.append(f"Line {i+1}: Type mismatch — assigning string to int")
            is_control = re.match(r'^(for|while|if)\s*\(', l)
            if l and not l.endswith((";", "{", "}")) and not l.startswith("#") and not l.endswith(":") and not is_control:
                errors.append(f"Line {i+1}: Missing semicolon")
            if "for(" in l and l.count(";") < 2:
                errors.append(f"Line {i+1}: Invalid for loop — missing semicolons in header")

        elif lang == "Java":
            match = re.search(r'String\s+(\w+)\s*=\s*([A-Za-z_]\w*)\s*;?$', l)
            if match:
                errors.append(f"Line {i+1}: Missing quotes for String '{match.group(1)}'")
            if re.search(r'int\s+\w+\s*=\s*".*"', l):
                errors.append(f"Line {i+1}: Type mismatch — assigning string to int")
            # Skip semicolon check for control-flow lines (for/while/if) ending with )
            is_control = re.match(r'^(for|while|if)\s*\(', l)
            if l and not l.endswith((";", "{", "}")) and not is_control:
                errors.append(f"Line {i+1}: Missing semicolon")
            if "for(" in l and l.count(";") < 2:
                errors.append(f"Line {i+1}: Invalid for loop — missing semicolons in header")

        elif lang == "Python":
            # Only flag control flow keywords missing a colon, not all lines
            if re.match(r'^\s*(if|for|while|def|class|elif|else|try|except|finally|with)\b.*[^:]$', l):
                errors.append(f"Line {i+1}: Missing ':' after control flow statement")

    return errors

# =============================
# FIX FOR LOOPS
# =============================
def fix_for_loop(line):
    # Strip trailing semicolon from the whole line first
    stripped = line.rstrip()
    if stripped.endswith(";"):
        stripped = stripped[:-1]
    line = stripped

    header_start = line.find("(")
    header_end = line.rfind(")")
    if header_start == -1 or header_end == -1:
        return line

    header = line[header_start + 1:header_end]

    # If already has 2 semicolons → valid, leave it alone
    if header.count(";") == 2:
        return line

    # Normalize: replace any existing semicolons with spaces so we
    # can re-split cleanly by the 3 logical parts
    header_clean = header.replace(";", " ").strip()

    # Pattern: init (type? var=num)  condition (var op val)  increment (var++ / ++var / var+=n)
    match = re.match(
        r'^((?:\w+\s+)?\w+\s*=\s*\d+)\s+'   # init:      e.g. "int i=0" or "i=0"
        r'(\w+\s*[<>!]=?\s*[\w\d]+)\s+'      # condition: e.g. "i<5" or "i<=n"
        r'(\w+\s*[\+\-]{2}|[\+\-]{2}\s*\w+|' # increment: post/pre ++ or --
        r'\w+\s*[\+\-]=\s*\d+)$',             #            or += / -=
        header_clean
    )

    if match:
        init  = match.group(1).strip()
        cond  = match.group(2).strip()
        incr  = match.group(3).strip()
    else:
        # Fallback: split on whitespace into at most 3 tokens
        tokens = header_clean.split()
        init  = tokens[0] if len(tokens) > 0 else ""
        cond  = tokens[1] if len(tokens) > 1 else ""
        incr  = tokens[2] if len(tokens) > 2 else ""

    fixed_header = f"{init}; {cond}; {incr}"
    suffix = line[header_end + 1:].strip()   # anything after ")" e.g. "{" or ""
    result = line[:header_start + 1] + fixed_header + ")"
    if suffix:
        result += " " + suffix
    return result

# =============================
# AUTO FIX
# =============================
def auto_fix(code):
    lines = code.split("\n")
    fixed = []
    lang = detect_language(code)

    for line in lines:
        l = line.strip()

        if lang == "C++":
            line = re.sub(r'int\s+(\w+)\s*=\s*"(\d+)"', r'int \1 = \2', line)
            line = re.sub(r'string\s+(\w+)\s*=\s*([A-Za-z_]\w*)\s*$', r'string \1 = "\2"', line)
            if l and l.startswith("#include") and l.endswith(";"):
                line = line.rstrip(";")
            if l and not l.endswith((";", "{", "}")) and not line.strip().startswith("#"):
                line += ";"
            if "for(" in line:
                line = fix_for_loop(line)
            line = re.sub(r'(if|while)\s*\((.*?)\)\s*;', r'\1(\2)', line)

        elif lang == "C":
            line = re.sub(r'int\s+(\w+)\s*=\s*"(\d+)"', r'int \1 = \2', line)
            line = re.sub(r"char\s+(\w+)\s*=\s*([A-Za-z])\b", r"char \1 = '\2'", line)
            if l and l.startswith("#include") and l.endswith(";"):
                line = line.rstrip(";")
            if l and not l.endswith((";", "{", "}")) and not line.strip().startswith("#"):
                line += ";"
            if "for(" in line:
                line = fix_for_loop(line)

        elif lang == "Java":
            line = re.sub(r'int\s+(\w+)\s*=\s*"(\d+)"', r'int \1 = \2', line)
            line = re.sub(r'String\s+(\w+)\s*=\s*([A-Za-z_]\w*)\s*$', r'String \1 = "\2"', line)
            if l and not l.endswith((";", "{", "}")):
                line += ";"
            if "for(" in line:
                line = fix_for_loop(line)

        elif lang == "Python":
            # Fix odd number of quotes (unclosed string)
            if line.count('"') % 2 != 0:
                line += '"'
            # Fix missing colon on control flow
            if re.match(r'^\s*(if|for|while|def|class|elif|else|try|except|finally|with)\b.*[^:]$', l):
                line += ":"
            # Remove stray semicolons after operators
            line = re.sub(r'([+\-*/])\s*;', r'\1', line)

        fixed.append(line)

    return "\n".join(fixed)

# =============================
# OPTIMIZATION TECHNIQUES
# =============================
def constant_folding(code):
    return re.sub(
        r'(\d+)\s*([\+\-\*/])\s*(\d+)',
        lambda m: safe_eval(m.group(1), m.group(2), m.group(3)),
        code
    )

def algebraic_simplification(code):
    code = re.sub(r'(\w+)\s*\+\s*0\b', r'\1', code)
    code = re.sub(r'\b0\s*\+\s*(\w+)', r'\1', code)
    code = re.sub(r'(\w+)\s*\*\s*1\b', r'\1', code)
    code = re.sub(r'\b1\s*\*\s*(\w+)', r'\1', code)
    code = re.sub(r'(\w+)\s*\*\s*0\b', '0', code)
    code = re.sub(r'\b0\s*\*\s*(\w+)', '0', code)
    code = re.sub(r'(\w+)\s*-\s*0\b', r'\1', code)
    return code

TYPE_KEYWORDS = {"int", "float", "double", "long", "short", "char", "bool",
                 "string", "String", "var", "auto", "unsigned", "signed"}

def extract_varname(lhs):
    """Strip C/C++/Java type keyword from LHS to get the bare variable name."""
    parts = lhs.strip().split()
    if len(parts) >= 2 and parts[0] in TYPE_KEYWORDS:
        return parts[-1]   # e.g. "int x" → "x", "String name" → "name"
    return parts[-1] if parts else lhs.strip()

def has_type_prefix(lhs):
    parts = lhs.strip().split()
    return len(parts) >= 2 and parts[0] in TYPE_KEYWORDS

def constant_propagation(lines):
    consts, result = {}, []
    for line in lines:
        if '=' in line:
            indent = len(line) - len(line.lstrip())
            prefix = line[:indent]
            lhs, expr = line.split('=', 1)
            lhs_clean = lhs.strip()          # e.g. "int a" or "a"
            expr = expr.strip().rstrip(';')
            semi = ';' if line.rstrip().endswith(';') else ''
            var_name = extract_varname(lhs_clean)
            # Register constant if RHS is a plain integer
            if expr.isdigit():
                consts[var_name] = expr
            else:
                # Substitute known constants into RHS
                for k, v in consts.items():
                    expr = re.sub(rf'\b{re.escape(k)}\b', v, expr)
                # After substitution, fold any new constant expressions
                expr = re.sub(
                    r'(\d+)\s*([\+\-\*/])\s*(\d+)',
                    lambda m: safe_eval(m.group(1), m.group(2), m.group(3)),
                    expr
                )
                # If result is now a plain number, register it too
                if expr.isdigit():
                    consts[var_name] = expr
            result.append(f"{prefix}{lhs_clean} = {expr}{semi}")
        else:
            result.append(line)
    return result

def copy_propagation(lines):
    copies, result = {}, []
    for line in lines:
        if '=' in line:
            indent = len(line) - len(line.lstrip())
            prefix = line[:indent]
            lhs, expr = line.split('=', 1)
            lhs_clean = lhs.strip()
            expr = expr.strip().rstrip(';')
            semi = ';' if line.rstrip().endswith(';') else ''
            var_name = extract_varname(lhs_clean)
            # Substitute if RHS is a known copy
            if expr in copies:
                expr = copies[expr]
            # Only record as copy alias for bare reassignments (no type prefix)
            if re.match(r'^\w+$', expr) and not has_type_prefix(lhs_clean):
                copies[var_name] = expr
            result.append(f"{prefix}{lhs_clean} = {expr}{semi}")
        else:
            result.append(line)
    return result

def dead_code_elimination(lines):
    seen, result = set(), []
    for line in reversed(lines):
        if '=' in line:
            lhs = line.split('=')[0]
            var_name = extract_varname(lhs)
            if var_name in seen:
                continue
            seen.add(var_name)
        result.append(line)
    return list(reversed(result))

def common_subexpression(lines):
    expr_map, result = {}, []
    for line in lines:
        if '=' in line:
            indent = len(line) - len(line.lstrip())
            prefix = line[:indent]
            lhs, expr = line.split('=', 1)
            lhs_clean = lhs.strip()
            expr = expr.strip().rstrip(';')
            semi = ';' if line.rstrip().endswith(';') else ''
            var_name = extract_varname(lhs_clean)
            # Only apply CSE for non-trivial expressions (not plain numbers/single words)
            is_trivial = bool(re.match(r'^\w+$', expr)) or expr.isdigit()
            if not is_trivial and expr in expr_map and expr_map[expr] != var_name:
                result.append(f"{prefix}{lhs_clean} = {expr_map[expr]}{semi}")
            else:
                if not is_trivial:
                    expr_map[expr] = var_name
                result.append(f"{prefix}{lhs_clean} = {expr}{semi}")
        else:
            result.append(line)
    return result

# =============================
# AI PREDICTION
# =============================
def hybrid_predict(code):
    if re.search(r'\d+\s*[\+\-\*/]\s*\d+', code):
        return "Constant Folding"
    if re.search(r'\w+\s*[\+\-\*/]\s*0\b|\w+\s*\*\s*1\b', code):
        return "Algebraic Simplification"
    if re.search(r'(\w+)\s*=\s*(\w+)\n.*\1\s*=', code):
        return "Dead Code Elimination"
    try:
        return model.predict(vectorizer.transform([code]))[0]
    except Exception:
        return "General Optimization"

# =============================
# OPTIMIZATION SCORE
# =============================
def optimization_score(before, after):
    before_chars = len(before.replace(" ", "").replace("\n", ""))
    after_chars = len(after.replace(" ", "").replace("\n", ""))
    if before_chars == 0:
        return 0
    reduction = (before_chars - after_chars) / before_chars
    return min(100, max(0, int(reduction * 100) + 10))

# =============================
# MAIN OPTIMIZER
# =============================
def optimize_code(code):
    applied_steps = []

    # Pass 1 — constant propagation first (substitutes known values into expressions)
    lines = code.split("\n")
    new_lines = constant_propagation(lines)
    if new_lines != lines:
        applied_steps.append("Constant Propagation")
    lines = new_lines
    code = "\n".join(lines)

    # Pass 2 — fold/simplify now that constants are substituted
    new_code = algebraic_simplification(code)
    if new_code != code:
        applied_steps.append("Algebraic Simplification")
    code = new_code

    new_code = constant_folding(code)
    if new_code != code:
        applied_steps.append("Constant Folding")
    code = new_code

    # Pass 3 — copy / dead-code / CSE on the folded result
    lines = code.split("\n")

    new_lines = copy_propagation(lines)
    if new_lines != lines:
        applied_steps.append("Copy Propagation")
    lines = new_lines

    new_lines = dead_code_elimination(lines)
    if new_lines != lines:
        applied_steps.append("Dead Code Elimination")
    lines = new_lines

    new_lines = common_subexpression(lines)
    if new_lines != lines:
        applied_steps.append("Common Subexpression Elimination")
    lines = new_lines

    if not applied_steps:
        applied_steps.append("No optimizations needed — code is already clean")

    return "\n".join(lines), applied_steps

# =============================
# REAL-TIME ERROR CHECK
# =============================
def real_time_check(event=None):
    code = input_text.get("1.0", tk.END)
    errors = detect_errors(code)
    error_box.delete("1.0", tk.END)
    if errors:
        for e in errors:
            error_box.insert(tk.END, e + "\n")
    else:
        error_box.insert(tk.END, "No errors detected ✅")

# =============================
# SYNTAX HIGHLIGHTING
# =============================
KEYWORDS = [
    "int", "float", "double", "long", "short", "char", "bool",
    "if", "else", "for", "while", "do", "return", "break", "continue",
    "def", "class", "import", "from", "as", "pass", "yield", "lambda",
    "String", "public", "private", "protected", "static", "void",
    "new", "this", "super", "true", "false", "null", "None",
    "string", "cout", "cin", "endl", "namespace", "using", "std",
    "print", "input", "range", "len", "in", "not", "and", "or",
]

def highlight_syntax(event=None):
    input_text.tag_remove("kw", "1.0", tk.END)
    input_text.tag_remove("str", "1.0", tk.END)
    input_text.tag_remove("comment", "1.0", tk.END)
    input_text.tag_remove("number", "1.0", tk.END)

    content = input_text.get("1.0", tk.END)

    # Keywords
    for kw in KEYWORDS:
        start = "1.0"
        while True:
            pos = input_text.search(rf'\b{kw}\b', start, stopindex=tk.END, regexp=True)
            if not pos:
                break
            end = f"{pos}+{len(kw)}c"
            input_text.tag_add("kw", pos, end)
            start = end

    # Strings (simple " " highlight)
    for match in re.finditer(r'"[^"]*"', content):
        start_idx = f"1.0+{match.start()}c"
        end_idx = f"1.0+{match.end()}c"
        input_text.tag_add("str", start_idx, end_idx)

    # Numbers
    for match in re.finditer(r'\b\d+(\.\d+)?\b', content):
        start_idx = f"1.0+{match.start()}c"
        end_idx = f"1.0+{match.end()}c"
        input_text.tag_add("number", start_idx, end_idx)

    # Single-line comments (// and #)
    for match in re.finditer(r'(//.*|#.*)', content):
        start_idx = f"1.0+{match.start()}c"
        end_idx = f"1.0+{match.end()}c"
        input_text.tag_add("comment", start_idx, end_idx)

    input_text.tag_config("kw", foreground="#ffcc00")
    input_text.tag_config("str", foreground="#98c379")
    input_text.tag_config("number", foreground="#d19a66")
    input_text.tag_config("comment", foreground="#5c6370", font=("Consolas", 11, "italic"))

# Combined key release handler (fixes the binding overwrite bug)
def on_key_release(event=None):
    real_time_check()
    highlight_syntax()


# =============================
# PDF UPLOAD
# =============================
def _extract_code_from_pdf(path):
    """Extract all text from a PDF file using pypdf."""
    reader = PdfReader(path)
    pages_text = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        if text.strip():
            pages_text.append(text)
    return "\n".join(pages_text)

def _clean_pdf_text(raw):
    """
    Lightly clean extracted PDF text so it loads nicely into the editor.
    - Remove form-feed characters
    - Normalise Windows line endings
    - Strip trailing whitespace per line
    - Remove completely blank duplicate lines (keep one blank line as separator)
    """
    text = raw.replace("\r\n", "\n").replace("\r", "\n").replace("\x0c", "\n")
    lines = text.split("\n")
    cleaned, prev_blank = [], False
    for line in lines:
        line = line.rstrip()
        is_blank = (line == "")
        if is_blank and prev_blank:
            continue          # collapse consecutive blank lines into one
        cleaned.append(line)
        prev_blank = is_blank
    return "\n".join(cleaned).strip()

def upload_pdf():
    if not PDF_AVAILABLE:
        messagebox.showerror(
            "pypdf not installed",
            "Install pypdf to use PDF upload:\n\n    pip install pypdf"
        )
        return

    path = filedialog.askopenfilename(
        title="Select a PDF file containing code",
        filetypes=[("PDF Files", "*.pdf"), ("All Files", "*.*")]
    )
    if not path:
        return

    result_label.config(text="Reading PDF... ⏳", fg="yellow")
    root.update_idletasks()

    def _worker():
        try:
            raw = _extract_code_from_pdf(path)
            if not raw.strip():
                root.after(0, lambda: (
                    result_label.config(text="PDF has no extractable text ❌", fg="red"),
                    messagebox.showwarning(
                        "Empty PDF",
                        "No text could be extracted from this PDF.\n"
                        "It may be a scanned image. Try a text-based PDF."
                    )
                ))
                return

            code = _clean_pdf_text(raw)
            fname = path.split("/")[-1].split("\\")[-1]   # basename, cross-platform

            def _insert():
                # Ask user: replace or append
                if input_text.get("1.0", tk.END).strip():
                    choice = messagebox.askyesnocancel(
                        "PDF Loaded",
                        f"'{fname}' loaded ({len(reader_pages)} page(s)).\n\n"
                        "Replace current content?\n"
                        "(No = Append at cursor, Cancel = abort)"
                    )
                    if choice is None:      # Cancel
                        result_label.config(text="PDF upload cancelled.", fg="#8b949e")
                        return
                    if choice:              # Yes — replace
                        input_text.delete("1.0", tk.END)
                else:
                    choice = True           # editor empty → just insert

                input_text.insert(tk.END, code)
                real_time_check()
                highlight_syntax()
                num_pages = len(PdfReader(path).pages)
                result_label.config(
                    text=f"PDF loaded: {fname}  ({num_pages} page{'s' if num_pages != 1 else ''}) 📄",
                    fg="#00ffcc"
                )

            # PdfReader already read; store page count for the lambda
            reader_pages = PdfReader(path).pages
            root.after(0, _insert)

        except Exception as e:
            root.after(0, lambda: (
                result_label.config(text=f"PDF error: {e}", fg="red"),
                messagebox.showerror("PDF Read Error", str(e))
            ))

    threading.Thread(target=_worker, daemon=True).start()

# =============================
# VOICE INPUT (threaded)
# =============================
def _voice_worker():
    if not SR_AVAILABLE:
        result_label.config(text="speech_recognition not installed", fg="red")
        return
    r = sr.Recognizer()
    try:
        with sr.Microphone() as source:
            result_label.config(text="Listening... 🎤", fg="yellow")
            root.update_idletasks()
            audio = r.listen(source, timeout=5)
        text = r.recognize_google(audio)
        input_text.insert(tk.END, text)
        result_label.config(text="Voice input added ✅", fg="#00ffcc")
    except sr.WaitTimeoutError:
        result_label.config(text="No speech detected", fg="red")
    except sr.UnknownValueError:
        result_label.config(text="Could not understand audio", fg="red")
    except sr.RequestError as e:
        result_label.config(text=f"API error: {e}", fg="red")
    except Exception as e:
        result_label.config(text=f"Voice error: {e}", fg="red")

def voice_input():
    t = threading.Thread(target=_voice_worker, daemon=True)
    t.start()

# =============================
# THEME TOGGLE
# =============================
is_dark = True

def toggle_theme():
    global is_dark
    if is_dark:
        root.configure(bg="#f0f0f0")
        input_text.configure(bg="#ffffff", fg="#1a1a1a", insertbackground="#1a1a1a")
        output_text.configure(bg="#ffffff", fg="#1a1a1a")
        error_box.configure(bg="#fff5f5", fg="#cc0000")
        result_label.configure(bg="#f0f0f0", fg="#555555")
        for w in frame.winfo_children():
            if isinstance(w, tk.Button):
                pass  # keep button colors
        frame.configure(bg="#f0f0f0")
        title_label.configure(bg="#f0f0f0")
        for lbl in info_labels:
            lbl.configure(bg="#f0f0f0")
        is_dark = False
    else:
        root.configure(bg="#0d1117")
        input_text.configure(bg="#161b22", fg="#e6edf3", insertbackground="white")
        output_text.configure(bg="#161b22", fg="#c9d1d9")
        error_box.configure(bg="#1e1e1e", fg="#ff6b6b")
        result_label.configure(bg="#0d1117", fg="#8b949e")
        frame.configure(bg="#0d1117")
        title_label.configure(bg="#0d1117")
        for lbl in info_labels:
            lbl.configure(bg="#0d1117")
        is_dark = True

# =============================
# COPY TO CLIPBOARD
# =============================
def copy_output():
    content = output_text.get("1.0", tk.END).strip()
    if content:
        root.clipboard_clear()
        root.clipboard_append(content)
        result_label.config(text="Output copied to clipboard 📋", fg="#00ffcc")

# =============================
# MAIN GUI FUNCTIONS
# =============================
def run_optimizer():
    code = input_text.get("1.0", tk.END).strip()
    if not code:
        result_label.config(text="Please enter some code first.", fg="orange")
        return

    lang = detect_language(code)
    suggestion = hybrid_predict(code)
    fixed = auto_fix(code)
    optimized, steps = optimize_code(fixed)
    errors = detect_errors(code)
    score = optimization_score(code, optimized)

    output_text.delete("1.0", tk.END)
    output_text.insert(tk.END, f"Language Detected : {lang}\n")
    output_text.insert(tk.END, f"AI Suggestion     : {suggestion}\n")
    output_text.insert(tk.END, "─" * 50 + "\n\n")

    output_text.insert(tk.END, "── FIXED CODE ──────────────────────────────────\n")
    output_text.insert(tk.END, fixed + "\n\n")

    output_text.insert(tk.END, "── OPTIMIZED CODE ──────────────────────────────\n")
    output_text.insert(tk.END, optimized + "\n\n")

    output_text.insert(tk.END, "── OPTIMIZATION STEPS APPLIED ──────────────────\n")
    for s in steps:
        output_text.insert(tk.END, f"  ✔ {s}\n")

    output_text.insert(tk.END, f"\n  🔥 Optimization Score : {score}/100\n")

    errors_after = detect_errors(fixed)
    if errors:
        output_text.insert(tk.END, "\n── ERRORS IN ORIGINAL CODE (auto-fixed above) ──\n")
        for e in errors:
            output_text.insert(tk.END, f"  ✖ {e}\n")
        if not errors_after:
            output_text.insert(tk.END, "\n  ✅ All errors resolved by auto-fix.\n")
        else:
            output_text.insert(tk.END, "\n── REMAINING ERRORS (manual fix needed) ────────\n")
            for e in errors_after:
                output_text.insert(tk.END, f"  ⚠ {e}\n")
    else:
        output_text.insert(tk.END, "\n  ✅ No syntax errors detected.\n")

    result_label.config(text="Optimization complete 🚀", fg="#00ffcc")

def save_output():
    file = filedialog.asksaveasfile(
        defaultextension=".txt",
        filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
    )
    if file:
        file.write(output_text.get("1.0", tk.END))
        file.close()
        result_label.config(text="Output saved ✅", fg="#00ffcc")

def clear_all():
    input_text.delete("1.0", tk.END)
    output_text.delete("1.0", tk.END)
    error_box.delete("1.0", tk.END)
    result_label.config(text="Cleared.", fg="#8b949e")

# =============================
# BUILD UI
# =============================
root = tk.Tk()
root.title("AI Code Optimizer")
root.geometry("1050x900")
root.configure(bg="#0d1117")
root.resizable(True, True)

info_labels = []

title_label = tk.Label(
    root,
    text=" AI Code Optimizer ",
    font=("Segoe UI", 20, "bold"),
    bg="#0d1117",
    fg="#58a6ff"
)
title_label.pack(pady=(14, 2))

sub_label = tk.Label(
    root,
    text="Detect errors • Auto-fix • Optimize • Highlight syntax",
    font=("Segoe UI", 9),
    bg="#0d1117",
    fg="#484f58"
)
sub_label.pack(pady=(0, 8))
info_labels.append(sub_label)

# Input label
in_label = tk.Label(root, text="  📝 Input Code", font=("Segoe UI", 10, "bold"),
                    bg="#0d1117", fg="#8b949e", anchor="w")
in_label.pack(fill=tk.X, padx=20)
info_labels.append(in_label)

input_text = scrolledtext.ScrolledText(
    root, height=11,
    font=("Consolas", 11),
    bg="#161b22", fg="#e6edf3",
    insertbackground="white",
    selectbackground="#264f78",
    relief=tk.FLAT,
    padx=10, pady=8
)
input_text.pack(fill=tk.BOTH, padx=20, pady=(2, 6))
input_text.bind("<KeyRelease>", on_key_release)

# Error box label
err_label = tk.Label(root, text="  ⚠ Real-time Error Check", font=("Segoe UI", 10, "bold"),
                     bg="#0d1117", fg="#8b949e", anchor="w")
err_label.pack(fill=tk.X, padx=20)
info_labels.append(err_label)

error_box = scrolledtext.ScrolledText(
    root, height=4,
    font=("Consolas", 10),
    bg="#1e1e1e", fg="#ff6b6b",
    insertbackground="white",
    relief=tk.FLAT,
    padx=10, pady=6
)
error_box.pack(fill=tk.BOTH, padx=20, pady=(2, 8))

# Button row
frame = tk.Frame(root, bg="#0d1117")
frame.pack(pady=4)

btn_cfg = {"font": ("Segoe UI", 10, "bold"), "width": 12, "relief": tk.FLAT,
           "cursor": "hand2", "pady": 6}

tk.Button(frame, text="▶ OPTIMIZE", command=run_optimizer,
          bg="#238636", fg="white", **btn_cfg).grid(row=0, column=0, padx=5)
tk.Button(frame, text="📄 PDF", command=upload_pdf,
          bg="#c05621", fg="white", **btn_cfg).grid(row=0, column=1, padx=5)
tk.Button(frame, text="🎤 VOICE", command=voice_input,
          bg="#bf8700", fg="white", **btn_cfg).grid(row=0, column=2, padx=5)
tk.Button(frame, text="📋 COPY", command=copy_output,
          bg="#1f6feb", fg="white", **btn_cfg).grid(row=0, column=3, padx=5)
tk.Button(frame, text="💾 SAVE", command=save_output,
          bg="#388bfd", fg="white", **btn_cfg).grid(row=0, column=4, padx=5)
tk.Button(frame, text="🗑 CLEAR", command=clear_all,
          bg="#da3633", fg="white", **btn_cfg).grid(row=0, column=5, padx=5)
tk.Button(frame, text="🌓 THEME", command=toggle_theme,
          bg="#6e40c9", fg="white", **btn_cfg).grid(row=0, column=6, padx=5)

# Output label
out_label = tk.Label(root, text="  📤 Output", font=("Segoe UI", 10, "bold"),
                     bg="#0d1117", fg="#8b949e", anchor="w")
out_label.pack(fill=tk.X, padx=20, pady=(10, 0))
info_labels.append(out_label)

output_text = scrolledtext.ScrolledText(
    root, height=16,
    font=("Consolas", 11),
    bg="#161b22", fg="#c9d1d9",
    insertbackground="white",
    selectbackground="#264f78",
    relief=tk.FLAT,
    padx=10, pady=8,
    state=tk.NORMAL
)
output_text.pack(fill=tk.BOTH, padx=20, pady=(2, 8))

result_label = tk.Label(
    root,
    text="Ready — paste your code and click OPTIMIZE",
    bg="#0d1117", fg="#484f58",
    font=("Segoe UI", 10)
)
result_label.pack(pady=(0, 12))

root.mainloop()