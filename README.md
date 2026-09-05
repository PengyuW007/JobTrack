# JobTrack
JobTrack is a Python based job application tracking system that automatically synchronizes job-related emails from Gmail, 
stores application records in SQLite, analyzes recruitment progress, and generates visual funnel reports.

## Features

### Gmail Synchronization

- Connects to Gmail using Gmail API
- Reads job-related emails automatically
- Supports incremental synchronization
- Avoids duplicate records

### Application Tracking

- Consolidates multiple emails into a single application record
- Tracks application status changes
- Stores company, position, sender, subject, and timestamps

### Recruitment Analytics

- Total applications
- Assessment count
- Interview count
- Rejection count
- Offer count
- Conversion rates

### Visualization

- Generates recruitment funnel charts
- Exports funnel reports as images

## Installation & API Setup

Clone the repository:
````
git clone https://github.com/yourusername/JobTrack.git
cd JobTrack
````
Create virtual environment:
````
python -m venv venv
````
Activate environment:

Windows:
````
venv\Scripts\activate
````
Install dependencies:
````
pip install -r requirements.txt
````

### Gmail API Setup
1. Create a Google Cloud Project
2. Enable Gmail API
3. Create OAuth Desktop Credentials
4. Download:
````
credentials.json
````
5. Place it in the project root directory
6. Run
````
python main.py
````

## Itinerary
````
Gmail API
  ↓
Email Parser
  ↓
SQLite
  ↓
Analytics Service/Email Classifier
  ↓
Visualization
````

## Tech Stack
- Python 
- Gmail API
  - google-api-python-client 
  - google-auth
- sqlite3

## Architecture
````
JobTrack
│
├── gmail/
│   └── Gmail API integration
│
├── parsers/
│   └── Email parsing logic
│
├── business/
│   ├── EmailClassifier
│   └── AnalyticsService
│
├── persistence/
│   ├── DataAccess
│   └── DataAccessJob
│
├── objects/
│   └── JobApplication
│
├── visualization/
│   └── FunnelChart
│
└── tracker.db
````

## Workflow
1. Create an OAuth Client using Google Cloud

2. Download credentials.json

3. Log in to Gmail for authorization on the first run of Python

4. Token.json will be automatically generated thereafter

5. Read new emails on each subsequent run

6. Remove duplicates based on message_id

7. Update the Excel or SQLite database

## Pseudo Code for Automatic Classification
````
if "interview" in text:
    status = "Interview"
elif "assessment" in text or "coding test" in text:
    status = "Assessment"
elif "unfortunately" in text or "not move forward" in text:
    status = "Rejected"
elif "thank you for applying" in text:
    status = "Applied"
elif "offer" in text or "congratulations" in text:
    status = "Offer"
else:
    status = "Unknown"
````
## 常驻工作台与历史查重

运行 `python main.py`，或在 Windows 使用 `venv\Scripts\pythonw.exe JobTrack.pyw`
启动不带命令行窗口的工作台（也可以将此命令建立为桌面快捷方式）。

- 日期、漏斗图和网址查重位于同一窗口。选择日历日期后点击“刷新图表”；快捷时间范围立即刷新。
- 在职位网址输入框粘贴链接，自动读取公开页面中的 JobPosting 结构化信息并查询全部本地投递历史。
- 查重独立于图表时间范围。结果提供历史日期、状态和匹配依据；选中一行可以查看完整日期。
- 相同网址会匹配邮件中的原始链接（忽略常见追踪参数，保留岗位编号参数）。
- 公司与岗位名称相同或相近时展示候选记录；关联过的职位描述高度一致时标记疑似换网址重发。
- 如果页面要求登录、依赖 JavaScript、没有唯一职位或拒绝读取，可手动补充公司、名称及描述，再点击“按补充信息查重”。
- 确认候选记录就是该次投递后，点击“确认同一投递并保存网址／描述”，为以后识别重发岗位保留依据。查询本身不会新增投递记录。

启动时后台同步 Gmail，窗口可继续查询本地数据。首次更新会补扫邮箱全部可见历史，保存完整相关邮件证据；成功完成后恢复增量同步。大邮箱第一次可能耗时较长，需要已有 Gmail 授权；失败会在窗口内显示，可点击“同步 Gmail”重试。

历史数据的限制：原版只保存 500 字符的邮件摘要，同公司岗位会合并。新增证据表保存每封相关邮件的原始日期和正文；“投递确认邮件”日期来自被识别为 Applied 的邮件，否则只标注“最早相关记录”。多封确认邮件不一定表示多次投递。邮件不包含职位描述时，无法凭空恢复旧描述，也无法保证识别所有重发岗位。“未找到匹配”不代表确定未投递。当前数据来源仍为 Gmail 和已有 SQLite 记录，不会扫描本地简历文件。

验证：`venv\Scripts\python.exe -m unittest discover -s tests -v`

### Resume recommendation

The English workbench uses a compact two-column layout: controls are on the left and the date-filtered funnel is on the right. Paste an Indeed or LinkedIn URL to parse it, check all application history, and recommend one of the selected PDF, DOCX, TXT, or Markdown resumes.

Set `OPENAI_API_KEY` to enable AI selection through the OpenAI Responses API. `JOBTRACK_OPENAI_MODEL` can override the default model. Without an API key, JobTrack uses a local skill-overlap score and labels the result `Local match`.
