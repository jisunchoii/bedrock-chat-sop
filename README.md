## 사전 준비사항

### 1. re-ranker 모델 배포 
Amazon SageMaker Studio 에서 `re-ranker.ipynb` 노트북을 실행합니다. 

- 필요 권한
    - AmazonSSMFullAccess


### 2. Document ingestion
```
# Docker 이미지 빌드
docker build -t my-lambda-image .

# ECR에 로그인
aws ecr get-login-password --region <your-region> | docker login --username AWS --password-stdin <account-id>.dkr.ecr.<your-region>.amazonaws.com

# ECR 리포지토리 생성 (이미 생성된 경우 건너뛰기)
aws ecr create-repository --repository-name my-lambda-repo

# Docker 이미지 태그 지정
docker tag my-lambda-image:latest <account-id>.dkr.ecr.<your-region>.amazonaws.com/my-lambda-repo:latest

# Docker 이미지 ECR에 푸시
docker push <account-id>.dkr.ecr.<your-region>.amazonaws.com/my-lambda-repo:latest
```

#### Lambda 함수 환경 변수
index_name : sop-genai-demo
opensearch_account : opensearch id
opensearch_passwd : opensearch password
opensearch_url : opensearch domain url 

### Lambda 함수 권한
- AmazonBedrockFullAccess
- AmazonOpenSearchServiceFullAccess
- AmazonS3FullAccess