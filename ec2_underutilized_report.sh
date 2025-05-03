#!/bin/bash

# ---------- CONFIG ----------
AWS_REGION="us-west-2"
EMAIL_TO="your_email@example.com"
EMAIL_SUBJECT="🚀 AWS Underutilized EC2 Report"
CSV_FILE="/home/ec2-user/ec2-report-poc/ec2_underutilized_report.csv"
LOG_FILE="/home/ec2-user/ec2-report-poc/ec2_report.log"

# ---------- INIT ----------
echo "$(date '+%F %T') - Starting report..." | tee -a "$LOG_FILE"
> "$CSV_FILE"
echo "Instance ID,Instance Type,CPU Utilization (%),Memory Utilization (%),Name,Recommendation" >> "$CSV_FILE"

# ---------- HTML Header ----------
HTML=$(cat <<EOF
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
<tr><th>Instance ID</th><th>Type</th><th>CPU Utilization</th><th>Memory Utilization</th><th>Name</th><th>Recommendation</th></tr>
EOF
)

# ---------- Fetch Instances ----------
INSTANCE_IDS=$(aws ec2 describe-instances --region "$AWS_REGION" --query "Reservations[].Instances[].InstanceId" --output text)

for INSTANCE_ID in $INSTANCE_IDS; do
    echo "$(date '+%F %T') - Checking $INSTANCE_ID" | tee -a "$LOG_FILE"

    NAME_TAG=$(aws ec2 describe-tags --region "$AWS_REGION" --filters "Name=resource-id,Values=$INSTANCE_ID" "Name=key,Values=Name" --query "Tags[0].Value" --output text)
    INSTANCE_TYPE=$(aws ec2 describe-instances --region "$AWS_REGION" --instance-ids "$INSTANCE_ID" --query "Reservations[].Instances[].InstanceType" --output text)

    CPU_UTIL=$(aws cloudwatch get-metric-statistics --region "$AWS_REGION" \
      --metric-name CPUUtilization --namespace AWS/EC2 \
      --dimensions Name=InstanceId,Value="$INSTANCE_ID" \
      --start-time $(date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%SZ) \
      --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
      --period 604800 --statistics Average \
      --query "Datapoints[0].Average" --output text)

    MEM_UTIL=$(aws cloudwatch get-metric-statistics --region "$AWS_REGION" \
      --metric-name mem_used_percent --namespace CWAgent \
      --dimensions Name=InstanceId,Value="$INSTANCE_ID" \
      --start-time $(date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%SZ) \
      --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
      --period 604800 --statistics Average \
      --query "Datapoints[0].Average" --output text)

    # Fallbacks
    [[ "$CPU_UTIL" == "None" || -z "$CPU_UTIL" ]] && CPU_UTIL=0
    [[ "$MEM_UTIL" == "None" || -z "$MEM_UTIL" ]] && MEM_UTIL=0
    CPU_UTIL=$(printf "%.2f" "$CPU_UTIL")
    MEM_UTIL=$(printf "%.2f" "$MEM_UTIL")

    # Badges
    [[ $(echo "$CPU_UTIL < 10" | bc) -eq 1 ]] && CPU_BADGE="<span class='badge-critical'>$CPU_UTIL%</span>" ||
    [[ $(echo "$CPU_UTIL < 30" | bc) -eq 1 ]] && CPU_BADGE="<span class='badge-warning'>$CPU_UTIL%</span>" ||
    CPU_BADGE="<span class='badge-good'>$CPU_UTIL%</span>"

    [[ $(echo "$MEM_UTIL < 30" | bc) -eq 1 ]] && MEM_BADGE="<span class='badge-warning'>$MEM_UTIL%</span>" ||
    MEM_BADGE="<span class='badge-good'>$MEM_UTIL%</span>"

    # Recommendation
    if (( $(echo "$CPU_UTIL < 10" | bc -l) )); then
        RECOMMENDATION="🔥 Consider downsizing"
    elif (( $(echo "$CPU_UTIL > 80" | bc -l) )); then
        RECOMMENDATION="⚠️ High usage - review"
    else
        RECOMMENDATION="📊 Monitor further"
    fi

    # Append to HTML and CSV
    HTML+="<tr><td>$INSTANCE_ID</td><td>$INSTANCE_TYPE</td><td>$CPU_BADGE</td><td>$MEM_BADGE</td><td>${NAME_TAG:-N/A}</td><td>$RECOMMENDATION</td></tr>"
    echo "$INSTANCE_ID,$INSTANCE_TYPE,$CPU_UTIL,$MEM_UTIL,${NAME_TAG:-N/A},$RECOMMENDATION" >> "$CSV_FILE"
done

HTML+="</table><p style='color:gray; font-size:12px;'>Generated on $(date)</p></body></html>"

# ---------- MIME EMAIL SEND ----------
(
echo "Subject: $EMAIL_SUBJECT"
echo "To: $EMAIL_TO"
echo "MIME-Version: 1.0"
echo "Content-Type: multipart/mixed; boundary=MAIL_BOUNDARY"
echo
echo "--MAIL_BOUNDARY"
echo "Content-Type: text/html; charset=UTF-8"
echo "Content-Disposition: inline"
echo
echo "$HTML"
echo
echo "--MAIL_BOUNDARY"
echo "Content-Type: text/csv"
echo "Content-Disposition: attachment; filename=\"$(basename $CSV_FILE)\""
echo
cat "$CSV_FILE"
echo "--MAIL_BOUNDARY--"
) | /usr/sbin/sendmail -t

echo "$(date '+%F %T') - Email sent successfully." | tee -a "$LOG_FILE"
