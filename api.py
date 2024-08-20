import os, sys, boto3
module_path = "../../.."
sys.path.append(os.path.abspath(module_path))
from utils.rag import prompt_repo, OpenSearchHybridSearchRetriever, OpenSearchLexicalSearchRetriever
from utils.opensearch import opensearch_utils
from utils.ssm import parameter_store

from langchain.chains import RetrievalQA
from langchain.embeddings import BedrockEmbeddings
from langchain_aws import ChatBedrock




region = boto3.Session().region_name
pm = parameter_store(region)

# 텍스트 생성 LLM 가져오기, streaming_callback을 인자로 받아옴
def get_llm(streaming_callback):
    model_kwargs = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 4096,
        "temperature" : 0,
        "top_k": 350,
        "top_p": 0.999
    }

    llm = ChatBedrock(
        model_id="anthropic.claude-3-5-sonnet-20240620-v1:0",  # 파운데이션 모델 설정
        model_kwargs=model_kwargs,  # Claud에 대한 속성 구성
        streaming=True,
        callbacks=[streaming_callback],
    )
    return llm

# 임베딩 모델 가져오기


def get_embedding_model():
    llm_emb = BedrockEmbeddings(model_id='amazon.titan-embed-text-v2:0')

    return llm_emb

# Opensearch vectorDB 가져오기

def get_opensearch_client():

    opensearch_domain_endpoint = pm.get_params(key='opensearch_domain_endpoint', enc=False)
    opensearch_user_id = pm.get_params(key='opensearch_userid', enc=False)
    opensearch_user_password = pm.get_params(key='opensearch_password', enc=True)

    opensearch_domain_endpoint = opensearch_domain_endpoint
    rag_user_name = opensearch_user_id
    rag_user_password = opensearch_user_password
    aws_region = os.environ.get("AWS_DEFAULT_REGION", None)
    http_auth = (rag_user_name, rag_user_password)

    os_client = opensearch_utils.create_aws_opensearch_client(
        aws_region,
        opensearch_domain_endpoint,
        http_auth
    )

    return os_client

# hybrid search retriever 만들기
def get_retriever(streaming_callback, parent, reranker):
    os_client = get_opensearch_client()
    llm_text = get_llm(streaming_callback)
    llm_emb = get_embedding_model()
    reranker_endpoint_name = pm.get_params(key="reranker_endpoint",enc=False)
    index_name = pm.get_params(key='opensearch_index_name', enc=False)

    opensearch_hybrid_retriever = OpenSearchHybridSearchRetriever(
        os_client=os_client,
        index_name=index_name,
        llm_text=llm_text,  # llm for query augmentation in both rag_fusion and HyDE
        llm_emb=llm_emb,  # Used in semantic search based on opensearch

        # option for lexical
        minimum_should_match=0,
        filter=[],

        # option for search
        # ["RRF", "simple_weighted"], rank fusion 방식 정의
        fusion_algorithm="RRF",
        # [for lexical, for semantic], Lexical, Semantic search 결과에 대한 최종 반영 비율 정의
        ensemble_weights=[.51, .49],
        reranker=reranker,  # enable reranker with reranker model
        # endpoint name for reranking model
        reranker_endpoint_name=reranker_endpoint_name,
        parent_document=parent,  # enable parent document

        # option for async search
        async_mode=True,

        # option for output
        k=6,  # 최종 Document 수 정의
        verbose=False,
    )

    return opensearch_hybrid_retriever

# 모델에 query하기
def invoke(query, streaming_callback, parent, reranker, violation):

    # llm, retriever 가져오기
    llm_text = get_llm(streaming_callback)
    opensearch_hybrid_retriever = get_retriever(streaming_callback, parent, reranker)

    # answer only 선택
    if violation: 
        PROMPT = prompt_repo.get_qa(prompt_type="violation_format_answer")
    else: 
        PROMPT = prompt_repo.get_qa(prompt_type="qna_format_answer")
        # PROMPT = prompt_repo.get_qa(prompt_type="answer_only")

    qa = RetrievalQA.from_chain_type(
        llm=llm_text,
        chain_type="stuff",
        retriever=opensearch_hybrid_retriever,
        return_source_documents=True,
        chain_type_kwargs={
            "prompt": PROMPT,
            "verbose": False,
        },
        verbose=False
    )

    response = qa(query)
    answer = response["result"]
    document = None
    source_documents = None
    
    if answer.startswith("No relevant context"):
        pass
    else:
        source_documents = response['source_documents']
        document = source_documents[0]

    if document:
        document_dict = document.__dict__
        metadata = document_dict.get('metadata', {})

    return answer, source_documents