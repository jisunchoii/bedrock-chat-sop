from langchain_community.vectorstores.opensearch_vector_search import OpenSearchVectorSearch
from langchain_community.embeddings import BedrockEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.docstore.document import Document
from opensearchpy import OpenSearch

from botocore.config import Config
import boto3
import os
import traceback
from urllib.parse import unquote_plus

from io import BytesIO
import PyPDF2


file_type = 'pdf'
bedrock_region = boto3.Session().region_name
index_name = os.environ.get('index_name')
opensearch_account = os.environ.get('opensearch_account')
opensearch_passwd = os.environ.get('opensearch_passwd')
opensearch_url = os.environ.get('opensearch_url')
opensearch_parent_key_name = "parent_id"
opensearch_family_tree_key_name = "family_tree"


def get_embedding():
    model_id = 'amazon.titan-embed-text-v2:0'
    
    # bedrock   
    boto3_bedrock = boto3.client(
        service_name='bedrock-runtime',
        region_name=bedrock_region, 
        config=Config(
            retries = {
                'max_attempts': 30
            }
        )
    )
    
    bedrock_embedding = BedrockEmbeddings(
        client=boto3_bedrock,
        region_name = bedrock_region,
        model_id = model_id
    )  
    
    return bedrock_embedding

# embedding for RAG
bedrock_embeddings = get_embedding()

# opensearch index 생성
os_client = OpenSearch(
    hosts = [{
        'host': opensearch_url.replace("https://", ""), 
        'port': 443
    }],
    http_compress = True,
    http_auth=(opensearch_account, opensearch_passwd),
    use_ssl = True,
    verify_certs = True,
    ssl_assert_hostname = False,
    ssl_show_warn = False,
)
 

vectorstore = OpenSearchVectorSearch(
    index_name=index_name,  
    is_aoss = False,
    #engine="faiss",  # default: nmslib
    embedding_function = bedrock_embeddings,
    opensearch_url = opensearch_url,
    http_auth=(opensearch_account, opensearch_passwd),
)  

def is_not_exist(index_name):    
    if os_client.indices.exists(index_name):        
        print('use exist index: ', index_name)    
        return False
    else:
        print('no index: ', index_name)
        return True
                       
def create_nori_index():
    index_body = {
        'settings': {
            'analysis': {
                'analyzer': {
                    'my_analyzer': {
                        'char_filter': ['html_strip'], 
                        'tokenizer': 'nori',
                        'filter': ['nori_number','lowercase','trim','my_nori_part_of_speech'],
                        'type': 'custom'
                    }
                },
                'tokenizer': {
                    'nori': {
                        'decompound_mode': 'mixed',
                        'discard_punctuation': 'true',
                        'type': 'nori_tokenizer'
                    }
                },
                "filter": {
                    "my_nori_part_of_speech": {
                        "type": "nori_part_of_speech",
                        "stoptags": [
                                "E", "IC", "J", "MAG", "MAJ",
                                "MM", "SP", "SSC", "SSO", "SC",
                                "SE", "XPN", "XSA", "XSN", "XSV",
                                "UNA", "NA", "VSV"
                        ]
                    }
                }
            },
            'index': {
                'knn': True,
                'knn.space_type': 'cosinesimil'  # Example space type
            }
        },
        'mappings': {
            'properties': {
                'metadata': {
                    'properties': {
                        'source' : {'type': 'keyword'},                    
                        'title': {'type': 'text'},  # For full-text search
                    }
                },            
                'text': {
                    'analyzer': 'my_analyzer',
                    'search_analyzer': 'my_analyzer',
                    'type': 'text'
                },
                'vector_field': {
                    'type': 'knn_vector',
                    'dimension': 1024  # Replace with your vector dimension
                }
            }
        }
    }
    if(is_not_exist(index_name)):
        try: # create index
            response = os_client.indices.create(
                index_name,
                body=index_body
            )
            print('index was created with nori plugin:', response)
            return response
        except Exception:
            err_msg = traceback.format_exc()
            print('error message: ', err_msg)                


def add_to(docs, family_tree_id_key, parent_id_key):
    ids = []
    parent_splitter = RecursiveCharacterTextSplitter(
        chunk_size=2000,
        chunk_overlap=100,
        separators=["\n\n", "\n", ".", " ", ""],
        length_function = len,
    )
    child_splitter = RecursiveCharacterTextSplitter(
        chunk_size=400,
        chunk_overlap=50,
        length_function = len,
    )

    parent_docs = parent_splitter.split_documents(docs)
    print('len(parent_docs): ', len(parent_docs))
    if len(parent_docs):
        for i, doc in enumerate(parent_docs):
            doc.metadata[family_tree_id_key] = 'parent'        
            doc.metadata[parent_id_key] = None

        try:        
            parent_doc_ids = vectorstore.add_documents(parent_docs, bulk_size = 10000)
            print('parent_doc_ids: ', parent_doc_ids)

            child_docs = []

            for i, doc in enumerate(parent_docs):
                _id = parent_doc_ids[i]
                sub_docs = child_splitter.split_documents([doc])
                for _doc in sub_docs:
                    _doc.metadata[family_tree_id_key] = 'child'                    
                    _doc.metadata[parent_id_key] = _id
                child_docs.extend(sub_docs)

            child_doc_ids = vectorstore.add_documents(child_docs, bulk_size = 10000)
            print('child_doc_ids: ', child_doc_ids)

            ids = parent_doc_ids+child_doc_ids
        except Exception:
            err_msg = traceback.format_exc()
            print('error message: ', err_msg)                          

# load documents from s3 for pdf and txt
def load_document(bucket, key):
    s3 = boto3.client('s3')
    doc = s3.get_object(Bucket=bucket, Key=key)

    if file_type == 'pdf':
        Byte_contents = doc.get('Body').read()
        reader = PyPDF2.PdfReader(BytesIO(Byte_contents))
        texts = []
        for page in reader.pages:
            texts.append(page.extract_text())
        contents = '\n'.join(texts)
    new_contents = str(contents).replace("\n"," ") 
    
    docs = []
    docs.append(Document(
        page_content=contents,
        metadata={
            'source' : key,
            'title' : key.split('.')[0]
        }
    ))
    add_to(docs,opensearch_family_tree_key_name, opensearch_parent_key_name)

def lambda_handler(event, context):
    for record in event['Records']:
        bucket = record['s3']['bucket']['name']
        key = record['s3']['object']['key']
        key = unquote_plus(key)

        print('bucket: ', bucket)
        print('key: ', key)
                
        s3EventInfo = {
            'event_timestamp': record['eventTime'],
            'bucket': bucket,
            'key': key,
            'type': record['eventName']
        }
        print(s3EventInfo)
        
        try: 
            create_nori_index()
            load_document(bucket, key)
        except Exception:
            err_msg = traceback.format_exc()
            print('error message: ', err_msg)                
    return {
        'statusCode': 200
    }