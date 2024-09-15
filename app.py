from flask import Flask, request, render_template
from radon.complexity import cc_visit, cc_rank
import requests

app = Flask(__name__)

# GitHub personal access token
GITHUB_TOKEN = 'GITHUB API KEY'

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/fetch_pr', methods=['POST'])
def fetch_pr():
    repo = request.form.get('repo')
    pr_number = request.form.get('pr_number')

    if not repo or not pr_number:
        return "Repository or PR Number is missing", 400

    
    url = f'https://api.github.com/repos/{repo}/pulls/{pr_number}'
    headers = {
        'Authorization': f'token {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github.v3+json'
    }

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        pr_data = response.json()
        pr_files_url = pr_data['url'] + '/files'
        files_response = requests.get(pr_files_url, headers=headers)

        if files_response.status_code == 200:
            files = files_response.json()

            # Run the quality checks
            merge_status = check_merge_conflicts(pr_data)
            pr_type = detect_pr_type(files)
            spam_status = detect_spam_pr(files)
            cyclomatic_results = cyclomatic_check(files)

            return f"""
            <h3>PR Quality Check</h3>
            <p>Merge Conflict Status: {merge_status}</p>
            <p>PR Type: {', '.join(pr_type)}</p>
            <p>Spam Check: {spam_status}</p>
            <h3>Cyclomatic Complexity Analysis:</h3>
            <pre>{cyclomatic_results}</pre>
            """
        else:
            return "Failed to fetch PR files.", 500
    else:
        return f"Failed to fetch PR details. Status Code: {response.status_code}", response.status_code

def check_merge_conflicts(pr_data):
    mergeable_status = pr_data.get('mergeable')
    if mergeable_status is None:
        return "Merge status pending."
    elif mergeable_status:
        return "No merge conflicts."
    else:
        return "This PR has merge conflicts."

def detect_pr_type(files):
    pr_type = []
    
    for file in files:
        filename = file['filename']
        
        if 'README.md' in filename:
            pr_type.append('README update')
        elif '/src/' in filename or '/lib/' in filename:
            pr_type.append('Feature or bug fix')
    
    if not pr_type:
        pr_type.append('Other changes')
    
    return pr_type

def detect_spam_pr(files):
    total_files = len(files)
    total_changes = sum(file['changes'] for file in files)
    
    # Simple heuristic: if there are many small, trivial changes, flag as potential spam
    if total_files == 1 and total_changes < 10:
        return "This PR is likely spam."
    return "This PR seems legitimate."

def cyclomatic_check(files):
    cyclomatic_report = []
    
    for file in files:
        if file['filename'].endswith('.py'):  
            file_content_url = file['raw_url']
            file_content = requests.get(file_content_url).text
            
            
            complexity_data = cc_visit(file_content)
            for block in complexity_data:
                cyclomatic_report.append(f"Function: {block.name}, Complexity: {block.complexity}, Rank: {cc_rank(block.complexity)}")

    return '\n'.join(cyclomatic_report) if cyclomatic_report else "No Python files analyzed for cyclomatic complexity."


def detect_languages(files):
    """Detect programming languages used in the PR based on file extensions."""
    language_map = {
        '.py': 'Python',
        '.js': 'JavaScript',
        '.html': 'HTML',
        '.css': 'CSS',
        '.java': 'Java',
        '.c': 'C',
        '.cpp': 'C++',
        '.rb': 'Ruby',
        '.php': 'PHP',
        '.go': 'Go',
        '.rs': 'Rust',
        '.swift': 'Swift',
        '.ts': 'TypeScript'
        
    }

    detected_languages = set()

    print("Files being analyzed for language detection:")  
    for file in files:
        filename = file['filename']
        print(f"Analyzing file: {filename}")  
        for ext, lang in language_map.items():
            if filename.endswith(ext):
                detected_languages.add(lang)
                print(f"Detected language: {lang} for file: {filename}") 

    if not detected_languages:
        return "No recognized programming languages found."
    
    return ', '.join(detected_languages)

if __name__ == '__main__':
    app.run(debug=True)
