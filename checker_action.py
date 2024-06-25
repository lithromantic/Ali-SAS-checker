import json
import requests
import logging
import os
from Tea.core import TeaCore
from typing import List
from alibabacloud_swas_open20200601.client import Client as SWAS_OPEN20200601Client
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_swas_open20200601 import models as swas_open20200601_models

# 初始化日志配置
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 从环境变量中获取阿里云的AccessKey ID和AccessKey Secret
access_key_id = os.getenv('ACCESS_KEY_ID')
print(f"id为：{access_key_id}")
access_key_secret = os.getenv('ACCESS_KEY_SECRET')
region_id = 'cn-hongkong'  # 例如：'cn-hangzhou'
alert_rate = 98  # 设置自动关机阀值 98为98%

# 从环境变量中获取Telegram的API Token和Chat ID
telegram_bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')

# 初始化 SWAS_OPEN20200601 客户端
def create_client() -> SWAS_OPEN20200601Client:
    config = open_api_models.Config(
        access_key_id=access_key_id,
        access_key_secret=access_key_secret,
    )
    config.endpoint = f"swas.{region_id}.aliyuncs.com"
    return SWAS_OPEN20200601Client(config)

client = create_client()

def send_telegram_message(message: str):
    url = f'https://api.telegram.org/bot{telegram_bot_token}/sendMessage'
    data = {'chat_id': telegram_chat_id, 'text': message}
    response = requests.post(url, data=data)
    if response.status_code != 200:
        logger.error(f"Failed to send message: {response.text}")

def stop_instance(instance_id: str):
    stop_request = swas_open20200601_models.StopInstanceRequest(instance_id=instance_id)
    response = client.stop_instance(stop_request)
    logger.info(f"Stopping instance {instance_id}: {response.body}")

def check_instances():
    list_instances_request = swas_open20200601_models.ListInstancesRequest()
    response = client.list_instances(list_instances_request)
    instances = response.body.instances
    instance_ids = [instance.instance_id for instance in instances if instance.status == 'Running']

    for instance in instances:
        logger.info(f"Instance: {instance.instance_name}, Expired: {instance.expired_time}, IP: {instance.public_ip_address}, Status: {instance.status}")

    formatted_instance_ids = json.dumps(instance_ids)

    list_traffic_packages_request = swas_open20200601_models.ListInstancesTrafficPackagesRequest(
        region_id=region_id,
        instance_ids=formatted_instance_ids
    )
    traffic_response = client.list_instances_traffic_packages(list_traffic_packages_request)
    traffic_json = TeaCore.to_map(traffic_response.body)["InstanceTrafficPackageUsages"]

    for usage in traffic_json:
        trafic_used_rate = usage['TrafficUsed'] / usage['TrafficPackageTotal'] * 100
        remaining_gb = usage['TrafficPackageRemaining'] / (1073741824)  # bytes to GB
        instance_id = usage['InstanceId']

        if trafic_used_rate > alert_rate:
            message = f"Instance {instance_id} has used more than 98% traffic. Shutting down."
            send_telegram_message(message)
            stop_instance(instance_id)
        else:
            logger.info(f"Instance {instance_id} has {remaining_gb:.1f} GB remaining traffic, already used {trafic_used_rate:.2f}%")

if __name__ == '__main__':
    check_instances()
