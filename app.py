import streamlit as st  # 모든 streamlit 명령은 "st" alias로 사용할 수 있습니다.
import api as glib2
from langchain.callbacks.base import BaseCallbackHandler
# from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler


class StreamHandler(BaseCallbackHandler):
    """
    Callback 핸들러를 사용하여 생성된 텍스트를 Streamlit에 스트리밍합니다.
    """

    def __init__(self, container: st.container) -> None:
        self.container = container
        self.text = ""

    def on_llm_new_token(self, token: str, **kwargs) -> None:
        """
        새로운 토큰을 텍스트에 추가하고 Streamlit 컨테이너를 업데이트합니다.
        """
        self.text += token
        self.container.markdown(self.text)

st.title("AWS SOP Q&A Bot with Advanced RAG!")  # page 제목
st.markdown('''- This chatbot is implemented using Amazon Bedrock Claude v3.5 Sonnet.''')

st.markdown('''- Integrated advanced RAG technology: **Hybrid Search, ReRanker** techniques.''')

st.markdown('''- The original data is stored in Amazon OpenSearch, and the embedding model utilizes Amazon Titan.''')

violation = False
col1, col2, col3 = st.columns([2, 1, 1])

with col3:
    violation = st.toggle("SOP Violation")

reranker = True
parent = False

if "messages" not in st.session_state:
    st.session_state["messages"] = [
        {"role": "assistant", "content": "안녕하세요. 저는 의약품 제조 공정 SOP Q&A 봇입니다. 질문을 입력하세요."}
    ]

for msg in st.session_state.messages:
    st.chat_message(msg["role"]).write(msg["content"])


# 유저가 쓴 chat을 query라는 변수에 담음
query = st.chat_input("Serach documentation")
if query:
    # Session에 메세지 저장
    st.session_state.messages.append({"role": "user", "content": query})
    
    # UI에 출력
    st.chat_message("user").write(query)
    st_cb = StreamHandler(st.empty())

    # ========================claude-3==========================================================
    # bedrock.py의 invoke 함수 사용
    # with st.chat_message("assistant"):
    response = glib2.invoke(query=query, streaming_callback=st_cb, parent=parent, reranker=reranker, violation=violation)
    # response 로 메세지, 링크, 레퍼런스(source_documents) 받아오게 설정된 것을 변수로 저장
    msg = response[0]
    ref = response[1]
    
    # Session 메세지 저장
    st.session_state.messages.append({"role": "assistant", "content": msg})
    # st.session_state.messages.append({"role": "assistant", "content": ref})

    # UI 출력
    # st.chat_message("assistant").write(msg)
    with st.expander("문서 출처", expanded=False):
        st.chat_message("assistant").write(ref)


    