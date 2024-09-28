from flask import Flask, render_template, request, jsonify
import requests
from datetime import datetime

app = Flask(__name__)

# GitHub personal access token
GITHUB_TOKEN = 'your_github_access_token'  # Replace this with your actual token

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/metrics', methods=['POST'])
def metrics():
    repo = request.json.get('repo')
    if not repo:
        return jsonify({"error": "Repository name is required."}), 400
    
    # Gather metrics
    metrics_data = gather_metrics(repo)
    return jsonify(metrics_data)

def gather_metrics(repo):
    headers = {'Authorization': f'token {GITHUB_TOKEN}'}
    
    # Fetch pull requests
    pr_url = f'https://api.github.com/repos/{repo}/pulls'
    pr_response = requests.get(pr_url, headers=headers)
    
    if pr_response.status_code != 200:
        return {"error": "Failed to fetch pull requests."}, 500

    pr_data = pr_response.json()

    # Fetch issues
    issues_url = f'https://api.github.com/repos/{repo}/issues'
    issues_response = requests.get(issues_url, headers=headers)
    
    if issues_response.status_code != 200:
        return {"error": "Failed to fetch issues."}, 500

    issues_data = issues_response.json()

    # Calculate metrics
    metrics = {
        "pr_counts": count_prs(pr_data),
        "issue_counts": count_issues(issues_data),
        "pr_response_time": calculate_response_time(pr_data),
        "average_merge_time": calculate_average_merge_time(pr_data),
        "contributor_activity": get_contributor_activity(repo),
        "issue_resolution_time": get_issue_resolution_time(repo),
        "average_size_of_prs": calculate_average_size_of_prs(pr_data),
        "code_churn": get_code_churn(repo)
    }
    
    return metrics

def count_prs(pr_data):
    open_prs = sum(1 for pr in pr_data if pr['state'] == 'open')
    closed_prs = sum(1 for pr in pr_data if pr['state'] == 'closed')
    merged_prs = sum(1 for pr in pr_data if pr.get('merged_at') is not None)
    
    return {
        "open": open_prs,
        "closed": closed_prs,
        "merged": merged_prs
    }

def count_issues(issue_data):
    open_issues = sum(1 for issue in issue_data if issue['state'] == 'open' and 'pull_request' not in issue)
    closed_issues = sum(1 for issue in issue_data if issue['state'] == 'closed' and 'pull_request' not in issue)

    return {
        "open": open_issues,
        "closed": closed_issues
    }

def calculate_average_size_of_prs(pr_data):
    total_lines_added = 0
    total_lines_removed = 0
    pr_count = 0
    
    for pr in pr_data:
        # Fetch commits for the pull request
        commits_url = pr['commits_url']
        commits_response = requests.get(commits_url, headers={'Authorization': f'token {GITHUB_TOKEN}'})
        commits_data = commits_response.json()

        for commit in commits_data:
            total_lines_added += commit.get('stats', {}).get('additions', 0)
            total_lines_removed += commit.get('stats', {}).get('deletions', 0)

        if commits_data:  # Count only if there are commits
            pr_count += 1

    average_lines_added = total_lines_added / pr_count if pr_count else 0
    average_lines_removed = total_lines_removed / pr_count if pr_count else 0

    return {"average_lines_added": average_lines_added, "average_lines_removed": average_lines_removed}

def calculate_response_time(pr_data):
    response_times = []
    for pr in pr_data:
        created_at = datetime.fromisoformat(pr['created_at'].replace("Z", "+00:00"))
        if pr.get('updated_at'):
            updated_at = datetime.fromisoformat(pr['updated_at'].replace("Z", "+00:00"))
            response_times.append((updated_at - created_at).total_seconds())
    return sum(response_times) / len(response_times) if response_times else 0

def calculate_average_merge_time(pr_data):
    merge_times = []
    for pr in pr_data:
        if pr.get('merged_at'):
            created_at = datetime.fromisoformat(pr['created_at'].replace("Z", "+00:00"))
            merged_at = datetime.fromisoformat(pr['merged_at'].replace("Z", "+00:00"))
            merge_times.append((merged_at - created_at).total_seconds())
    return sum(merge_times) / len(merge_times) if merge_times else 0

def get_contributor_activity(repo):
    contributors_url = f'https://api.github.com/repos/{repo}/contributors'
    contributors_response = requests.get(contributors_url, headers={'Authorization': f'token {GITHUB_TOKEN}'})
    if contributors_response.status_code != 200:
        return {"error": "Failed to fetch contributor activity."}, 500
    
    contributors_data = contributors_response.json()
    return [{"login": c['login'], "contributions": c['contributions']} for c in contributors_data]

def get_issue_resolution_time(repo):
    issues_url = f'https://api.github.com/repos/{repo}/issues'
    issues_response = requests.get(issues_url, headers={'Authorization': f'token {GITHUB_TOKEN}'})
    if issues_response.status_code != 200:
        return {"error": "Failed to fetch issues."}, 500
    
    issues_data = issues_response.json()
    resolution_times = []
    
    for issue in issues_data:
        if issue['state'] == 'closed':
            created_at = datetime.fromisoformat(issue['created_at'].replace("Z", "+00:00"))
            closed_at = datetime.fromisoformat(issue['closed_at'].replace("Z", "+00:00"))
            resolution_times.append((closed_at - created_at).total_seconds())

    return sum(resolution_times) / len(resolution_times) if resolution_times else 0

def get_code_churn(repo):
    # Fetch commits and calculate code churn (lines added and removed)
    commits_url = f'https://api.github.com/repos/{repo}/commits'
    commits_response = requests.get(commits_url, headers={'Authorization': f'token {GITHUB_TOKEN}'})
    if commits_response.status_code != 200:
        return {"error": "Failed to fetch commits."}, 500
    
    commits_data = commits_response.json()
    code_churn = {"lines_added": 0, "lines_removed": 0}
    
    for commit in commits_data:
        stats_url = commit['url'] + '/stats'
        stats_response = requests.get(stats_url, headers={'Authorization': f'token {GITHUB_TOKEN}'})
        if stats_response.status_code == 200:
            stats_data = stats_response.json()
            code_churn["lines_added"] += stats_data.get('additions', 0)
            code_churn["lines_removed"] += stats_data.get('deletions', 0)

    return code_churn

if __name__ == '__main__':
    app.run(debug=True)
