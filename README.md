# AWS SOP Q&A Chatbot with Advanced RAG Technology

This project implements an AWS SOP (Standard Operating Procedure) Q&A chatbot using advanced RAG (Retrieval Augmented Generation) technology. The chatbot leverages Amazon Bedrock Claude v3.5 Sonnet for natural language processing and integrates with Amazon OpenSearch for data storage and Amazon Titan for embeddings.

The chatbot provides an interactive interface for users to ask questions about AWS SOPs and receive accurate, context-aware responses. It utilizes hybrid search and reranking techniques to enhance the quality and relevance of the generated answers.

## Repository Structure

- `api.py`: Contains the core API functionality for the question-answering system.
- `app.py`: Implements the Streamlit-based user interface for the chatbot.
- `document-lambda/lambda_function.py`: Lambda function for processing and indexing PDF documents.
- `utils/opensearch.py`: Utility functions for interacting with OpenSearch.
- `utils/rag.py`: Implements RAG-related functions and prompt templates.
- `utils/ssm.py`: Utility class for interacting with AWS Systems Manager Parameter Store.
- `veeva-lambda/lambda_function.py`: Lambda function for downloading documents from Veeva Vault and storing them in S3.

## Usage Instructions

### Installation

Prerequisites:
- Python 3.8+
- AWS CLI configured with appropriate permissions
- Streamlit
- Boto3
- LangChain
- OpenSearch-py

To install the required dependencies:

```bash
pip install streamlit boto3 langchain opensearch-py
```

### Getting Started

1. Set up the necessary AWS resources:
   - Amazon Bedrock with Claude v3.5 Sonnet model
   - Amazon OpenSearch domain
   - Amazon S3 bucket for document storage
   - AWS Lambda functions for document processing

2. Configure the AWS credentials and region in your environment.

3. Set the required environment variables:
   - `AWS_DEFAULT_REGION`: Your AWS region
   - `OPENSEARCH_DOMAIN_ENDPOINT`: Your OpenSearch domain endpoint
   - `OPENSEARCH_INDEX_NAME`: The name of your OpenSearch index
   - `RERANKER_ENDPOINT`: The endpoint for your reranker model (if used)

4. Run the Streamlit application:

```bash
streamlit run app.py
```

### Configuration Options

The chatbot can be configured with the following options:
- Toggle SOP Violation mode
- Enable/disable reranking
- Adjust the number of retrieved documents
- Modify the prompt templates in `utils/rag.py`

### Common Use Cases

1. Asking questions about AWS SOPs:
   Users can input questions related to AWS Standard Operating Procedures, and the chatbot will provide relevant answers based on the indexed documents.

2. Analyzing SOP violations:
   When the SOP Violation mode is enabled, the chatbot can analyze documents for potential violations and provide suggestions for improvement.

3. Document indexing:
   The Lambda functions can be used to automatically process and index new documents added to the S3 bucket or downloaded from Veeva Vault.

### Testing & Quality

To ensure the quality of the chatbot:
1. Regularly update the document index with the latest SOPs and guidelines.
2. Test the chatbot with a variety of questions to ensure accurate and relevant responses.
3. Monitor the OpenSearch performance and adjust the indexing strategy if needed.

### Troubleshooting

Common issues and solutions:
- If the chatbot returns "No relevant context," check if the documents are properly indexed in OpenSearch.
- For slow response times, consider optimizing the OpenSearch query or adjusting the number of retrieved documents.
- If the Lambda functions fail, check the CloudWatch logs for error messages and ensure proper permissions are set.

## Data Flow

The request data flow through the application follows these steps:

1. User inputs a question through the Streamlit interface.
2. The question is sent to the API layer (`api.py`).
3. The API layer retrieves the language model and embedding model.
4. The question is processed by the hybrid search retriever, which combines lexical and semantic search using OpenSearch.
5. Relevant documents are retrieved and potentially reranked.
6. The retrieved context and question are passed to the language model for answer generation.
7. The generated answer is streamed back to the Streamlit interface.

```
[User] -> [Streamlit UI] -> [API Layer] -> [Hybrid Search Retriever]
                                              |
                                              v
[OpenSearch] <-> [Embedding Model] <-> [Language Model]
                                              |
                                              v
[User] <- [Streamlit UI] <- [API Layer] <- [Generated Answer]
```

Note: The document processing flow involves separate Lambda functions that index documents into OpenSearch, which are then used by the main application flow.