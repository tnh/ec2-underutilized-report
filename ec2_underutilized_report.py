#!/usr/bin/env python3
"""
EC2 Underutilized Instances Report Generator

This script identifies underutilized EC2 instances in AWS and generates a comprehensive
report with recommendations for cost optimization.

Features:
- Collects multiple utilization metrics (CPU, memory, network, disk I/O)
- Provides detailed, actionable recommendations based on utilization patterns
- Generates both HTML and CSV reports
- Sends email notifications with the reports attached
"""

import boto3
import datetime
import logging
import os
import sys
import csv
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from typing import Dict, List, Any, Tuple, Optional

# ---------- CONFIG ----------
AWS_REGION = "us-west-2"
EMAIL_TO = "your_email@example.com"
EMAIL_SUBJECT = "🚀 AWS Underutilized EC2 Report"
CSV_FILE = "/home/ec2-user/ec2-report-poc/ec2_underutilized_report.csv"
LOG_FILE = "/home/ec2-user/ec2-report-poc/ec2_report.log"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class EC2UtilizationReport:
    """Class responsible for generating EC2 utilization reports"""
    
    def __init__(self, region: str, csv_file: str):
        """
        Initialize the EC2UtilizationReport class
        
        Args:
            region: AWS region to query
            csv_file: Path to save the CSV report
        """
        self.region = region
        self.csv_file = csv_file
        self.ec2_client = boto3.client('ec2', region_name=region)
        self.cloudwatch_client = boto3.client('cloudwatch', region_name=region)
        self.instances_data = []
    
    def get_all_instance_ids(self) -> List[str]:
        """
        Get all EC2 instance IDs in the region
        
        Returns:
            List of EC2 instance IDs
        """
        try:
            paginator = self.ec2_client.get_paginator('describe_instances')
            instance_ids = []
            
            for page in paginator.paginate():
                for reservation in page['Reservations']:
                    for instance in reservation['Instances']:
                        # Only include running instances
                        if instance['State']['Name'] == 'running':
                            instance_ids.append(instance['InstanceId'])
            
            return instance_ids
        except Exception as e:
            logger.error(f"Error getting instance IDs: {e}")
            return []
    
    def get_instance_name(self, instance_id: str) -> str:
        """
        Get the Name tag value for an instance
        
        Args:
            instance_id: The EC2 instance ID
            
        Returns:
            The Name tag value or 'N/A' if not found
        """
        try:
            response = self.ec2_client.describe_tags(
                Filters=[
                    {'Name': 'resource-id', 'Values': [instance_id]},
                    {'Name': 'key', 'Values': ['Name']}
                ]
            )
            
            if response['Tags']:
                return response['Tags'][0]['Value']
            return "N/A"
        except Exception as e:
return response['Tags'][0]['Value']
            return "N/A"
        except Exception as e:
            # import re  # Used for sanitizing the error message
            sanitized_error = re.sub(r'[\r
]', '', str(e))  # Remove newline characters
            logger.error(f"Error getting instance name for {instance_id}: {sanitized_error}")
            return "N/A"
            return "N/A"
    
    def get_instance_type(self, instance_id: str) -> str:
        """
        Get the instance type for an EC2 instance
        
        Args:
            instance_id: The EC2 instance ID
            
        Returns:
            The EC2 instance type or 'Unknown' if not found
        """
        try:
            response = self.ec2_client.describe_instances(InstanceIds=[instance_id])
            return response['Reservations'][0]['Instances'][0]['InstanceType']
        except Exception as e:
            logger.error(f"Error getting instance type for {instance_id}: {e}")
            return "Unknown"
    
    def get_cloudwatch_metric(self, instance_id: str, metric_name: str, 
                             namespace: str, statistic: str = "Average") -> float:
        """
        Get CloudWatch metric data for an instance
        
        Args:
            instance_id: The EC2 instance ID
            metric_name: Name of the CloudWatch metric
            namespace: CloudWatch namespace
            statistic: Statistic to retrieve (Average, Maximum, etc.)
            
        Returns:
            The metric value or 0 if not available
        """
        try:
            end_time = datetime.datetime.utcnow()
            start_time = end_time - datetime.timedelta(days=7)
            
            response = self.cloudwatch_client.get_metric_statistics(
                Namespace=namespace,
                MetricName=metric_name,
                Dimensions=[{'Name': 'InstanceId', 'Value': instance_id}],
                StartTime=start_time,
                EndTime=end_time,
                Period=604800,  # 7 days in seconds
                Statistics=[statistic]
            )
            
            if response['Datapoints']:
                return response['Datapoints'][0][statistic]
            return 0
        except Exception as e:
            logger.error(f"Error getting {metric_name} for {instance_id}: {e}")
            return 0
    
    def get_instance_metrics(self, instance_id: str) -> Dict[str, Any]:
        """
        Get all metrics for an EC2 instance
        
        Args:
            instance_id: The EC2 instance ID
            
        Returns:
            Dictionary containing all instance metrics and metadata
        """
        logger.info(f"Checking instance {instance_id}")
        
        # Get instance metadata
        name_tag = self.get_instance_name(instance_id)
        instance_type = self.get_instance_type(instance_id)
        
        # Get utilization metrics
        cpu_util = self.get_cloudwatch_metric(
            instance_id, 'CPUUtilization', 'AWS/EC2')
        mem_util = self.get_cloudwatch_metric(
            instance_id, 'mem_used_percent', 'CWAgent')
        
        # Get enhanced metrics
        network_in = self.get_cloudwatch_metric(
            instance_id, 'NetworkIn', 'AWS/EC2')
        network_out = self.get_cloudwatch_metric(
            instance_id, 'NetworkOut', 'AWS/EC2')
        disk_read = self.get_cloudwatch_metric(
            instance_id, 'DiskReadBytes', 'AWS/EC2')
        disk_write = self.get_cloudwatch_metric(
            instance_id, 'DiskWriteBytes', 'AWS/EC2')
        
        # Format metrics to 2 decimal places
        cpu_util = round(cpu_util, 2)
        mem_util = round(mem_util, 2)
        network_in = round(network_in / (1024 * 1024), 2)  # Convert to MB
        network_out = round(network_out / (1024 * 1024), 2)  # Convert to MB
        disk_read = round(disk_read / (1024 * 1024), 2)  # Convert to MB
        disk_write = round(disk_write / (1024 * 1024), 2)  # Convert to MB
        
        # Generate recommendation based on usage patterns
        recommendation = self.generate_recommendation(
            cpu_util, mem_util, network_in, network_out)
        
        return {
            'instance_id': instance_id,
            'name': name_tag,
            'instance_type': instance_type,
            'cpu_util': cpu_util,
            'mem_util': mem_util,
            'network_in': network_in,
            'network_out': network_out,
            'disk_read': disk_read,
            'disk_write': disk_write,
            'recommendation': recommendation
        }
    
    def generate_recommendation(self, cpu_util: float, mem_util: float,
                               network_in: float, network_out: float) -> str:
        """
        Generate a detailed recommendation based on instance utilization
        
        Args:
            cpu_util: CPU utilization percentage
            mem_util: Memory utilization percentage
            network_in: Network in (MB)
            network_out: Network out (MB)
            
        Returns:
            A recommendation string
        """
        if cpu_util < 5 and mem_util < 20:
            return "🔥 Consider stopping or terminating this idle instance"
        elif cpu_util < 10 and mem_util < 30:
            return "🔄 Downsize to a smaller instance type (e.g., t3.micro)"
        elif cpu_util < 20 and mem_util < 40:
            return "💰 Consider switching to a cost-effective Spot Instance"
        elif cpu_util > 80 or mem_util > 80:
            return "⚠️ High usage - review and possibly upgrade"
        else:
            return "📊 Monitor further - utilization looks reasonable"
    
    def collect_all_instances_data(self) -> None:
        """
        Collect data for all EC2 instances and store in self.instances_data
        """
        instance_ids = self.get_all_instance_ids()
        logger.info(f"Found {len(instance_ids)} instances")
        
        self.instances_data = []
        for instance_id in instance_ids:
            instance_data = self.get_instance_metrics(instance_id)
            self.instances_data.append(instance_data)
    
    def generate_csv_report(self) -> None:
        """
        Generate a CSV report from the collected instance data
        """
        try:
            with open(self.csv_file, 'w', newline='') as csvfile:
                fieldnames = ['Instance ID', 'Instance Type', 'CPU Utilization (%)',
                             'Memory Utilization (%)', 'Network In (MB)',
                             'Network Out (MB)', 'Disk Read (MB)', 'Disk Write (MB)',
                             'Name', 'Recommendation']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                writer.writeheader()
                for instance in self.instances_data:
                    writer.writerow({
                        'Instance ID': instance['instance_id'],
                        'Instance Type': instance['instance_type'],
                        'CPU Utilization (%)': instance['cpu_util'],
                        'Memory Utilization (%)': instance['mem_util'],
                        'Network In (MB)': instance['network_in'],
                        'Network Out (MB)': instance['network_out'],
                        'Disk Read (MB)': instance['disk_read'],
                        'Disk Write (MB)': instance['disk_write'],
                        'Name': instance['name'],
                        'Recommendation': instance['recommendation']
                    })
            logger.info(f"CSV report generated: {self.csv_file}")
        except Exception as e:
            logger.error(f"Error generating CSV report: {e}")
    
    def generate_html_content(self) -> str:
        """
        Generate HTML content for the email report
        
        Returns:
            HTML string for the email body
        """
        html = """
        <html><head><style>
        body { font-family: sans-serif; background: #f4f6f9; padding: 20px; }
        table { width: 100%; border-collapse: collapse; }
        th { background-color: #2c3e50; color: #ecf0f1; padding: 10px; }
        td { border: 1px solid #ccc; padding: 10px; text-align: center; }
        tr:nth-child(even) { background-color: #ecf0f1; }
        .badge-critical { background: #e74c3c; color: white; padding: 4px 8px; border-radius: 5px; }
        .badge-warning { background: #f39c12; color: white; padding: 4px 8px; border-radius: 5px; }
        .badge-good { background: #2ecc71; color: white; padding: 4px 8px; border-radius: 5px; }
        </style></head><body>
        <h2>🚀 Underutilized EC2 Instances Report</h2>
        <table>
        <tr>
            <th>Instance ID</th>
            <th>Type</th>
            <th>CPU Utilization</th>
            <th>Memory Utilization</th>
            <th>Network In/Out (MB)</th>
            <th>Disk I/O (MB)</th>
            <th>Name</th>
            <th>Recommendation</th>
        </tr>
        """
        
        for instance in self.instances_data:
            # Determine CPU badge
            if instance['cpu_util'] < 10:
                cpu_badge = f"<span class='badge-critical'>{instance['cpu_util']}%</span>"
            elif instance['cpu_util'] < 30:
                cpu_badge = f"<span class='badge-warning'>{instance['cpu_util']}%</span>"
            else:
                cpu_badge = f"<span class='badge-good'>{instance['cpu_util']}%</span>"
            
            # Determine Memory badge
            if instance['mem_util'] < 30:
                mem_badge = f"<span class='badge-warning'>{instance['mem_util']}%</span>"
            else:
                mem_badge = f"<span class='badge-good'>{instance['mem_util']}%</span>"
            
            # Network and Disk I/O
            network = f"{instance['network_in']} / {instance['network_out']}"
            disk_io = f"{instance['disk_read']} / {instance['disk_write']}"
            
            html += f"""
            <tr>
                <td>{instance['instance_id']}</td>
                <td>{instance['instance_type']}</td>
                <td>{cpu_badge}</td>
                <td>{mem_badge}</td>
                <td>{network}</td>
                <td>{disk_io}</td>
                <td>{instance['name']}</td>
                <td>{instance['recommendation']}</td>
            </tr>
            """
        
        html += f"""
        </table>
        <p style='color:gray; font-size:12px;'>Generated on {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </body></html>
        """
        
        return html
    
    def send_email_report(self, to_email: str, subject: str) -> None:
        """
        Send email with HTML report and CSV attachment
        
        Args:
            to_email: Recipient email address
            subject: Email subject
        """
        try:
            msg = MIMEMultipart()
            msg['From'] = 'ec2-report@example.com'
            msg['To'] = to_email
            msg['Subject'] = subject
            
            # HTML body
            html_content = self.generate_html_content()
            msg.attach(MIMEText(html_content, 'html'))
            
            # CSV attachment
            with open(self.csv_file, 'rb') as file:
                attachment = MIMEApplication(file.read())
                attachment.add_header(
                    'Content-Disposition', 
                    'attachment', 
                    filename=os.path.basename(self.csv_file)
                )
                msg.attach(attachment)
            
            # Send email
            with smtplib.SMTP('localhost') as server:
                server.send_message(msg)
                
            logger.info("Email report sent successfully")
        except Exception as e:
            logger.error(f"Error sending email: {e}")
    
    def run(self, to_email: str, subject: str) -> None:
        """
        Execute the full report generation workflow
        
        Args:
            to_email: Recipient email address
            subject: Email subject
        """
        logger.info("Starting EC2 utilization report generation")
        self.collect_all_instances_data()
        self.generate_csv_report()
        self.send_email_report(to_email, subject)
        logger.info("Report generation complete")


def main():
    """Main entry point for the script"""
    try:
        report = EC2UtilizationReport(AWS_REGION, CSV_FILE)
        report.run(EMAIL_TO, EMAIL_SUBJECT)
    except KeyboardInterrupt:
        logger.info("Process interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()