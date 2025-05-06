# 📊 EC2 Underutilized Instance Report

`ec2_underutilized_report.py` is a Python script that identifies underutilized EC2 instances based on CloudWatch metrics and generates comprehensive utilization reports. It provides average CPU and memory utilization data using boto3 to access AWS CloudWatch. The script generates a colorful HTML table and sends an email with a CSV attachment for cost optimization tracking.

## 🔧 Features
✅ CPU Usage: Gathers 7-day average from CloudWatch  
✅ Memory Stats: Collects from CWAgent metrics  
✅ EC2 Metadata: Captures instance ID, type, and Name tag  
✅ Recommendations: Suggests downsizing when applicable  
✅ Email Report: Sends HTML email + CSV attachment  
✅ Logging: Configurable logging to both file and stdout  
✅ Multiple Output Formats: Generates both HTML and CSV reports

## 📁 Script Overview

💻 **CPU Usage** - Uses boto3 to retrieve `CPUUtilization` metrics from CloudWatch

🧠 **Memory Usage** - Uses boto3 to access CWAgent `mem_used_percent` (if configured)

🖥 **EC2 Metadata** - Fetches instance type and Name tag via boto3 EC2 API

📧 **Email Output** - Sends via SMTP using Python's email package with HTML formatting

📎 **CSV Report** - Provides a spreadsheet of the collected data for further analysis

## 🚀 Usage

```python
# Import the module
from ec2_underutilized_report import EC2UtilizationReport

# Initialize with region and output file
report = EC2UtilizationReport(region="us-west-2", csv_file="/path/to/output.csv")

# Run the full report process
report.run()
```

Or run directly from command line:

```bash
# Make the script executable:
chmod +x ec2_underutilized_report.py

# Run the script:
./ec2_underutilized_report.py
```

## 📦 Dependencies
- boto3
- Python 3.6+
- AWS IAM role with appropriate CloudWatch and EC2 permissions

## 🔍 Key Methods

The `EC2UtilizationReport` class provides the following methods:

- `get_all_instance_ids()`: Retrieves all running EC2 instance IDs
- `get_instance_name()`: Gets the Name tag of an instance
- `get_instance_type()`: Retrieves the instance type
- `get_cloudwatch_metric()`: Fetches metrics from CloudWatch
- `generate_recommendation()`: Creates advice based on utilization patterns
- `collect_all_instances_data()`: Gathers all instance data
- `generate_csv_report()`: Creates a CSV file with the report
- `generate_html_content()`: Generates a styled HTML report
- `send_email_report()`: Emails the HTML report with CSV attachment

## 🧪 Testing

The code includes a comprehensive test suite using pytest. To run the tests:

```bash
pytest -v test_ec2_underutilized_report.py
```

Tests cover all key functionality including:
- Instance data collection
- CloudWatch metric retrieval 
- Recommendation generation
- Report formatting and sending

## 🕒 Pro Tip
Schedule via cron to get regular reports:

```bash
0 8 * * * /path/to/ec2_underutilized_report.py
```