#!/usr/bin/env python3
"""
Unit tests for the EC2 Underutilized Instances Report Generator.
Tests validate core functionality including metrics collection, recommendation
generation, and report formatting.
"""

import pytest
import boto3
import datetime
from unittest.mock import patch, MagicMock, mock_open
import os
import sys

# Add the parent directory to the path to import the module under test
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Import the module to test
from ec2_underutilized_report import EC2UtilizationReport


class TestEC2UtilizationReport:
    """Test cases for the EC2UtilizationReport class"""

    @pytest.fixture
    def report(self):
        """Fixture that returns an instance of EC2UtilizationReport"""
        with patch('boto3.client'):
            return EC2UtilizationReport("us-west-2", "/tmp/test_report.csv")

    def test_init(self, report):
        """Test initialization of EC2UtilizationReport"""
        assert report.region == "us-west-2"
        assert report.csv_file == "/tmp/test_report.csv"
        assert hasattr(report, "ec2_client")
        assert hasattr(report, "cloudwatch_client")
        assert report.instances_data == []

    @patch('boto3.client')
    def test_get_all_instance_ids(self, mock_boto3, report):
        """Test getting all EC2 instance IDs"""
        # Setup mock response
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [
            {
                'Reservations': [
                    {
                        'Instances': [
                            {'InstanceId': 'i-12345678', 'State': {'Name': 'running'}},
                            {'InstanceId': 'i-87654321', 'State': {'Name': 'stopped'}}
                        ]
                    }
                ]
            }
        ]
        report.ec2_client.get_paginator.return_value = mock_paginator
        
        # Call the method
        result = report.get_all_instance_ids()
        
        # Assert results
        assert len(result) == 1
        assert result[0] == 'i-12345678'
        report.ec2_client.get_paginator.assert_called_once_with('describe_instances')

    @patch('boto3.client')
    def test_get_instance_name(self, mock_boto3, report):
        """Test getting an instance name from its tags"""
        # Setup mock response
        report.ec2_client.describe_tags.return_value = {
            'Tags': [{'Value': 'test-server'}]
        }
        
        # Call the method
        result = report.get_instance_name('i-12345678')
        
        # Assert results
        assert result == 'test-server'
        report.ec2_client.describe_tags.assert_called_once()

    @patch('boto3.client')
    def test_get_instance_name_no_tags(self, mock_boto3, report):
        """Test getting an instance name when no tags exist"""
        # Setup mock response
        report.ec2_client.describe_tags.return_value = {'Tags': []}
        
        # Call the method
        result = report.get_instance_name('i-12345678')
        
        # Assert results
        assert result == 'N/A'

    @patch('boto3.client')
    def test_get_instance_type(self, mock_boto3, report):
        """Test getting an instance type"""
        # Setup mock response
        report.ec2_client.describe_instances.return_value = {
            'Reservations': [
                {
                    'Instances': [{'InstanceType': 't3.micro'}]
                }
            ]
        }
        
        # Call the method
        result = report.get_instance_type('i-12345678')
        
        # Assert results
        assert result == 't3.micro'
        report.ec2_client.describe_instances.assert_called_once_with(
            InstanceIds=['i-12345678'])

    @patch('boto3.client')
    def test_get_cloudwatch_metric(self, mock_boto3, report):
        """Test getting CloudWatch metrics"""
        # Setup mock response
        now = datetime.datetime.utcnow()
        report.cloudwatch_client.get_metric_statistics.return_value = {
            'Datapoints': [{'Average': 15.5}]
        }
        
        # Call the method
        result = report.get_cloudwatch_metric(
            'i-12345678', 'CPUUtilization', 'AWS/EC2')
        
        # Assert results
        assert result == 15.5
        report.cloudwatch_client.get_metric_statistics.assert_called_once()

    @patch('boto3.client')
    def test_get_cloudwatch_metric_no_data(self, mock_boto3, report):
        """Test getting CloudWatch metrics when no data is available"""
        # Setup mock response
        report.cloudwatch_client.get_metric_statistics.return_value = {
            'Datapoints': []
        }
        
        # Call the method
        result = report.get_cloudwatch_metric(
            'i-12345678', 'CPUUtilization', 'AWS/EC2')
        
        # Assert results
        assert result == 0

    def test_generate_recommendation_idle(self, report):
        """Test recommendation generation for idle instances"""
        recommendation = report.generate_recommendation(3.0, 15.0, 5.0, 5.0)
        assert "stopping or terminating" in recommendation

    def test_generate_recommendation_low_usage(self, report):
        """Test recommendation generation for low usage instances"""
        recommendation = report.generate_recommendation(8.0, 25.0, 10.0, 10.0)
        assert "Downsize" in recommendation

    def test_generate_recommendation_medium_usage(self, report):
        """Test recommendation generation for medium usage instances"""
        recommendation = report.generate_recommendation(15.0, 35.0, 20.0, 20.0)
        assert "Spot Instance" in recommendation

    def test_generate_recommendation_high_usage(self, report):
        """Test recommendation generation for high usage instances"""
        recommendation = report.generate_recommendation(85.0, 90.0, 500.0, 500.0)
        assert "High usage" in recommendation

    def test_generate_recommendation_normal_usage(self, report):
        """Test recommendation generation for normal usage instances"""
        recommendation = report.generate_recommendation(50.0, 60.0, 100.0, 100.0)
        assert "reasonable" in recommendation

    @patch.object(EC2UtilizationReport, 'get_all_instance_ids')
    @patch.object(EC2UtilizationReport, 'get_instance_metrics')
    def test_collect_all_instances_data(self, mock_get_metrics, mock_get_ids, report):
        """Test collecting data for all instances"""
        # Setup mocks
        mock_get_ids.return_value = ['i-12345678', 'i-87654321']
        mock_get_metrics.side_effect = [
            {'instance_id': 'i-12345678', 'cpu_util': 5.0},
            {'instance_id': 'i-87654321', 'cpu_util': 80.0}
        ]
        
        # Call the method
        report.collect_all_instances_data()
        
        # Assert results
        assert len(report.instances_data) == 2
        assert report.instances_data[0]['instance_id'] == 'i-12345678'
        assert report.instances_data[1]['instance_id'] == 'i-87654321'
        mock_get_ids.assert_called_once()
        assert mock_get_metrics.call_count == 2

    @patch('builtins.open', new_callable=mock_open)
    def test_generate_csv_report(self, mock_file, report):
        """Test CSV report generation"""
        # Setup test data
        report.instances_data = [
            {
                'instance_id': 'i-12345678',
                'instance_type': 't3.micro',
                'cpu_util': 5.0,
                'mem_util': 20.0,
                'network_in': 10.0,
                'network_out': 5.0,
                'disk_read': 2.0,
                'disk_write': 1.0,
                'name': 'test-server',
                'recommendation': 'Test recommendation'
            }
        ]
        
        # Call the method
        report.generate_csv_report()
        
        # Assert file was opened correctly
        mock_file.assert_called_once_with(report.csv_file, 'w', newline='')
        # Assert write operations occurred
        handle = mock_file()
        assert handle.write.call_count > 0

    def test_generate_html_content(self, report):
        """Test HTML content generation"""
        # Setup test data
        report.instances_data = [
            {
                'instance_id': 'i-12345678',
                'instance_type': 't3.micro',
                'cpu_util': 5.0,
                'mem_util': 20.0,
                'network_in': 10.0,
                'network_out': 5.0,
                'disk_read': 2.0,
                'disk_write': 1.0,
                'name': 'test-server',
                'recommendation': 'Test recommendation'
            }
        ]
        
        # Call the method
        html = report.generate_html_content()
        
        # Assert HTML contains expected elements
        assert 'i-12345678' in html
        assert 't3.micro' in html
        assert 'badge-critical' in html  # Low CPU usage gets critical badge
        assert 'badge-warning' in html   # Low memory usage gets warning badge
        assert 'test-server' in html
        assert 'Test recommendation' in html

    @patch('smtplib.SMTP')
    @patch('builtins.open', new_callable=mock_open, read_data=b'test data')
    def test_send_email_report(self, mock_file, mock_smtp, report):
        """Test email sending functionality"""
        # Setup mocks
        report.generate_html_content = MagicMock(return_value='<html>Test</html>')
        report.csv_file = '/tmp/test.csv'
        
        # Call the method
        report.send_email_report('test@example.com', 'Test Subject')
        
        # Assert SMTP calls were made
        mock_smtp.assert_called_once_with('localhost')
        smtp_instance = mock_smtp.return_value.__enter__.return_value
        assert smtp_instance.send_message.call_count == 1

    @patch.object(EC2UtilizationReport, 'collect_all_instances_data')
    @patch.object(EC2UtilizationReport, 'generate_csv_report')
    @patch.object(EC2UtilizationReport, 'send_email_report')
    def test_run(self, mock_send_email, mock_gen_csv, mock_collect_data, report):
        """Test the full workflow execution"""
        # Call the method
        report.run('test@example.com', 'Test Subject')
        
        # Assert all component methods were called
        mock_collect_data.assert_called_once()
        mock_gen_csv.assert_called_once()
        mock_send_email.assert_called_once_with('test@example.com', 'Test Subject')


if __name__ == '__main__':
    pytest.main(['-v', 'test_ec2_underutilized_report.py'])