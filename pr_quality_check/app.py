from flask import Flask, request, render_template
from radon.complexity import cc_visit, cc_rank
import requests
from pygments.lexers import guess_lexer
from pygments.util import ClassNotFound

app = Flask(__name__)

# GitHub personal access token
GITHUB_TOKEN = 'your_github_access_token'

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/fetch_pr', methods=['POST'])
def fetch_pr():
    repo = request.form.get('repo')
    pr_number = request.form.get('pr_number')

    if not repo or not pr_number:
        return render_template('error.html', message="Repository or PR number is missing."), 400

    # Fetch PR details
    url = f'https://api.github.com/repos/{repo}/pulls/{pr_number}'
    headers = {
        'Authorization': f'token {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github.v3+json'
    }

    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return render_template('error.html', message=f"Failed to fetch PR details. Status Code: {response.status_code}"), response.status_code

    pr_data = response.json()

    # Fetch PR files
    pr_files_url = pr_data['url'] + '/files'
    files_response = requests.get(pr_files_url, headers=headers)
    if files_response.status_code != 200:
        return render_template('error.html', message="Failed to fetch PR files."), 500

    files = files_response.json()

    # Initialize language detection list
    language_detection = []

    # Run quality checks
    merge_status = check_merge_conflicts(pr_data)
    pr_type = detect_pr_type(files)
    spam_status = detect_spam_pr(files)
    cyclomatic_results = cyclomatic_check(files)

    # Detect the language for each file
    for file in files:
        if file['raw_url']:
            file_content = requests.get(file['raw_url']).text
            detected_language = detect_language(file_content)
            language_detection.append(f"{file['filename']}: {detected_language}")

    return render_template(
        'pr_quality_check.html',
        merge_status=merge_status,
        pr_type=pr_type,
        spam_status=spam_status,
        cyclomatic_results=format_cyclomatic_results(cyclomatic_results),
        language_detection=language_detection
    )

def check_merge_conflicts(pr_data):
    mergeable_status = pr_data.get('mergeable')
    if mergeable_status is None:
        return "Merge status pending."
    return "No merge conflicts." if mergeable_status else "This PR has merge conflicts."

def detect_pr_type(files):
    pr_type = []
    for file in files:
        filename = file['filename']
        if 'README.md' in filename:
            pr_type.append('README update')
        elif '/src/' in filename or '/lib/' in filename:
            pr_type.append('Feature or bug fix')
    return pr_type if pr_type else ['Other changes']

def detect_spam_pr(files):
    total_files = len(files)
    total_changes = sum(file['changes'] for file in files)
    if total_files == 1 and total_changes < 10:
        return "This PR is likely spam."
    return "This PR seems legitimate."

# Updated helper function to calculate and display overall cyclomatic complexity rank
def format_cyclomatic_results(cyclomatic_results):
    if not cyclomatic_results:
        return "No cyclomatic complexity data available."

    total_complexity = sum(result['complexity'] for result in cyclomatic_results)
    num_functions = len(cyclomatic_results)

    # Calculate the average cyclomatic complexity
    average_complexity = total_complexity / num_functions if num_functions > 0 else 0

    # Determine the overall rank based on the average complexity
    overall_rank = cc_rank(average_complexity)

    # Format the overall result
    return f"The overall cyclomatic complexity is {average_complexity:.2f}, with an overall rank of {overall_rank}."


def cyclomatic_check(files):
    cyclomatic_report = []
    for file in files:
        if file['filename'].endswith('.py'):
            file_content_url = file['raw_url']
            file_content = requests.get(file_content_url).text
            complexity_data = cc_visit(file_content)
            for block in complexity_data:
                cyclomatic_report.append({
                    'name': block.name,
                    'complexity': block.complexity,
                    'rank': cc_rank(block.complexity)
                })
    return cyclomatic_report

def detect_language(file_content):
    try:
        lexer = guess_lexer(file_content)
        return lexer.name  
    except ClassNotFound:
        return "Language could not be determined"

if __name__ == '__main__':
    app.run(debug=True)
