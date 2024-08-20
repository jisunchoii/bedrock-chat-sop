import os
import boto3
import json
import requests
from botocore.exceptions import ClientError


# AWS S3 클라이언트 초기화
s3_client = boto3.client('s3')

# S3 버킷 이름
bucket_name = os.environ.get('bucket_name')
secret_name = os.environ.get('secret_name')
region_name = boto3.Session().region_name
dynamodb = boto3.resource('dynamodb', region_name=region_name)
table = dynamodb.Table('veeva_documents')


# Veeva Vault API 정보
VERSION = os.environ.get('veeva_version')
DOMAIN = os.environ.get('veeva_domain')
API_ENDPOINT = f'https://{DOMAIN}.veevavault.com/api/{VERSION}/'


def get_secret(secret_name):
    # Create a Secrets Manager client
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=region_name
    )
    try:
        get_secret_value_response = client.get_secret_value(
            SecretId=secret_name
        )
    except ClientError as e:
        raise e

    secret = get_secret_value_response['SecretString']
    return secret

def get_session_id(secret_name):
    secret = json.loads(get_secret(secret_name))
    USERNAME = secret['username']
    PASSWORD = secret['password']

    auth_url = f'{API_ENDPOINT}auth'
    auth_data = {'username': USERNAME, 'password': PASSWORD}
    auth_response = requests.post(auth_url, data=auth_data)
    if auth_response.status_code == 200:
        auth_data = auth_response.json()
        session_id = auth_data['sessionId']
        print(f'Session ID obtained: {session_id}')
        return session_id
    else:
        print(f'Failed to obtain session ID. Error: {auth_response.text}')
        raise Exception('Failed to obtain session ID')


def download_documents(session_id):
    # 문서 목록 검색 API 호출
    search_url = f'{API_ENDPOINT}objects/documents'
    params = {
        'limit': 100,  # 한 번에 가져올 문서 수 (최대 100)
    }
    headers = {
        'Authorization': session_id  # 세션 ID를 헤더에 포함
    }

    response = requests.get(search_url, params=params, headers=headers)
    print(f"Search API response: {response.text}")  # 응답 내용 출력

    
    # 응답 처리
    if response.status_code == 200:
        documents = response.json()['documents']

        # 각 문서 다운로드 및 S3에 업로드
        for doc in documents:
            document_id = doc['document']['id']
            version_id =  doc['document']['version_id']
            filename = doc['document']['filename__v']
            download_url = f'{API_ENDPOINT}objects/documents/{document_id}/file'
            file_response = requests.get(download_url, headers=headers)  # 세션 ID 추가
            print(f"Download API response for document {document_id}: {file_response.text}")  # 응답 내용 출력
            
            if file_response.status_code == 200:
                file_data = file_response.content
                # DynamoDB에서 document_id 검색
                response = table.get_item(Key={'document_id': document_id})
                
                if 'Item' in response:
                    existing_version_id = response['Item'].get('version_id')
                    if existing_version_id == version_id:
                        # 동일한 버전이면 패스
                        print(f"Document {document_id}/{version_id}/{filename} already exists. Skipping.")
                        continue
                    else:
                        # 문서가 존재하지만 버전이 다르면 S3에서 삭제하고 새로운 버전으로 저장
                        file_key = f'documents/{document_id}/{version_id}/{filename}'
                        s3_client.put_object(Bucket=bucket_name, Key=file_key, Body=file_data)
                        print(f"Uploaded document {document_id}/{version_id}/{filename} to S3 and updated in DynamoDB")
                
                else:
                    # 문서가 없으면 S3에 업로드하고 DynamoDB에 저장
                    file_key = f'documents/{document_id}/{version_id}/{filename}'
                    s3_client.put_object(Bucket=bucket_name, Key=file_key, Body=file_data)
                    table.put_item(Item={
                        'document_id': document_id,
                        'version_id': version_id,
                        'filename': filename
                    })
                    print(f"Uploaded document {document_id}/{version_id}/{filename} to S3 and added to DynamoDB")
            else:
                print(f'Failed to get document list. Error: {response.text}')

    print('Documents downloaded and uploaded to S3 successfully.')
    return {
        'statusCode': 200,
        'body': json.dumps('Documents downloaded and uploaded to S3 successfully.')
    }


def lambda_handler(event, context):
    try:
        session_id = get_session_id(secret_name)
        download_documents(session_id)
        
        return {
            'statusCode': 200,
            'body': json.dumps('SUCCESS.')
        }
    
    
    except Exception as e:
        print(e)
        return {
            'statusCode': 500,
            'body': json.dumps('Failed to download and upload documents.')
        }