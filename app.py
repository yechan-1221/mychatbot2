import os
import json
import time
import base64
import requests
import streamlit as st
from datetime import datetime
from zoneinfo import ZoneInfo
from openai import AzureOpenAI
from dotenv import load_dotenv

# ==========================================
# 0. 페이지 설정 (가장 위에 위치해야 함)
# ==========================================
st.set_page_config(page_title="마지여행사 AI 대시보드", page_icon="✈️", layout="wide")

load_dotenv()
azure_oai_endpoint = os.getenv("AZURE_OAI_ENDPOINT")
azure_oai_key = os.getenv("AZURE_OAI_KEY")
azure_oai_deployment = os.getenv("AZURE_OAI_DEPLOYMENT")
weather_api_key = os.getenv("OPENWEATHER_API_KEY")

# ==========================================
# 1. 로컬 함수 정의
# ==========================================
def multiply_numbers(a, b):
    return a * b

def get_weather(location, unit="c"):
    if not weather_api_key:
        return json.dumps({"error": "OPENWEATHER_API_KEY가 설정되지 않았습니다."})
    units_param = "metric" if unit.lower() == "c" else "imperial"
    url = f"http://api.openweathermap.org/data/2.5/weather?q={location}&appid={weather_api_key}&units={units_param}&lang=kr"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        return json.dumps({
            "temperature": round(data["main"]["temp"], 1),
            "condition": data["weather"][0]["description"],
            "humidity": data["main"]["humidity"],
            "unit": "C" if unit.lower() == "c" else "F"
        })
    except requests.exceptions.RequestException:
        return json.dumps({"error": "날씨 정보를 가져올 수 없습니다. 도시 이름을 영문으로 확인해주세요."})

def fetch_startup_info():
    try:
        now = datetime.now(ZoneInfo("Asia/Seoul"))
        am_pm = "오후" if now.hour >= 12 else "오전"
        hour_12 = now.hour % 12 if now.hour % 12 != 0 else 12
        time_str = f"{now.year}년 {now.month}월 {now.day}일\n{am_pm} {hour_12}시 {now.minute}분"
        
        weather_res = json.loads(get_weather("Seoul", "c"))
        if "error" in weather_res:
            weather_str = "날씨 정보 오류"
        else:
            weather_str = f"{weather_res['temperature']}°C\n{weather_res['condition']}\n습도: {weather_res['humidity']}%"
        return f"**📍 현재 서울**\n\n{time_str}\n\n**🌤️ 날씨**\n\n{weather_str}"
    except Exception:
        return "정보를 불러오는 중 오류가 발생했습니다."

# ==========================================
# 2. 클라이언트 및 Assistant 초기화 (캐싱)
# ==========================================
@st.cache_resource
def get_azure_client_and_assistant():
    """Streamlit이 새로고침될 때마다 Assistant가 무한 생성되는 것을 방지합니다."""
    client = AzureOpenAI(
        azure_endpoint=azure_oai_endpoint,
        api_key=azure_oai_key,
        api_version="2024-05-01-preview"
    )
    
    assistant = client.beta.assistants.create(
        name="마지여행사 AI",
        model=azure_oai_deployment,
        instructions="당신은 마지여행사의 친절한 고객 지원 및 데이터 분석 AI 어시스턴트입니다. 고객의 질문에 친절하게 답변하고, 요청 시 데이터를 분석하여 그래프를 그려주며, 첨부된 문서의 내용을 정확하게 요약해 줍니다. 단, 파이썬으로 그래프를 그릴 때 제목, x축, y축 등 모든 라벨은 반드시 **영어(English)**로 작성하세요. 날씨 정보와 계산 결과는 줄바꿈과 볼드체를 사용하여 깔끔하게 정리해주세요.",
        tools=[
            {"type": "file_search"}, 
            {"type": "code_interpreter"},
            {"type": "function", "function": {"name": "get_weather", "description": "위치의 현재 날씨 확인", "parameters": {"type": "object", "properties": {"location": {"type": "string"}}, "required": ["location"]}}},
            {"type": "function", "function": {"name": "multiply_numbers", "description": "두 숫자 곱하기", "parameters": {"type": "object", "properties": {"a": {"type": "number"}, "b": {"type": "number"}}, "required": ["a", "b"]}}}
        ],
        tool_resources={"file_search": {"vector_store_ids": ["vs_oSZp7w2hLhqvhXpiI4l9FQoH"]}, "code_interpreter": {"file_ids": []}},
        temperature=0.7,
        top_p=1
    )
    return client, assistant

client, assistant = get_azure_client_and_assistant()

# ==========================================
# 3. 세션 상태 (Session State) 관리
# ==========================================
if "thread_id" not in st.session_state:
    st.session_state.thread_id = client.beta.threads.create().id
if "messages" not in st.session_state:
    st.session_state.messages = [] # 화면에 보여줄 대화 내역

# ==========================================
# 4. Streamlit UI 구성 (대시보드)
# ==========================================

# --- 사이드바 ---
with st.sidebar:
    st.markdown("### 🌍 실시간 정보")
    st.info(fetch_startup_info())
    
    st.markdown("---")
    st.markdown("### 📁 파일 첨부")
    uploaded_file = st.file_uploader("이미지, PDF, CSV 등을 업로드하세요.", type=["pdf", "csv", "txt", "png", "jpg", "jpeg", "webp"])
    
    st.markdown("---")
    if st.button("🗑️ 모든 대화 지우기", use_container_width=True):
        st.session_state.messages = []
        st.session_state.thread_id = client.beta.threads.create().id
        st.rerun()

# --- 메인 화면 ---
st.title("✈️ 마지여행사 AI 대시보드")
st.markdown("**지원 기능:** 여행사 정보 질의응답 | 데이터 기반 그래프 시각화 | 파일(.pdf, .csv 등) 요약 및 분석")
st.divider()

# 기존 대화 내역 출력
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg.get("text"):
            st.markdown(msg["text"])
        if msg.get("images"):
            for img_bytes in msg["images"]:
                st.image(img_bytes)

# ==========================================
# 5. 채팅 입력 및 백엔드 처리 로직
# ==========================================
if user_input := st.chat_input("질문하거나 요청을 입력하세요..."):
    
    display_input = user_input
    message_content = user_input
    attachments = []
    
    # 5-1. 업로드된 파일 처리 로직
    if uploaded_file is not None:
        file_name = uploaded_file.name
        ext = os.path.splitext(file_name)[1].lower()
        file_bytes = uploaded_file.getvalue() # Streamlit 메모리에서 파일 읽기
        
        # 이미지 파일 처리 (Vision Base64)
        if ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
            base64_image = base64.b64encode(file_bytes).decode('utf-8')
            mime_type = 'jpeg' if ext == '.jpg' else ext.replace('.', '')
            
            message_content = [
                {"type": "text", "text": user_input if user_input else "이 이미지를 분석해주세요."},
                {"type": "image_url", "image_url": {"url": f"data:image/{mime_type};base64,{base64_image}"}}
            ]
            display_input = f"🖼️ **[첨부된 이미지: {file_name}]**\n\n{user_input}"
            
        # 일반 문서 파일 처리 (Code Interpreter / File Search)
        else:
            # Azure OpenAI에 파일 업로드
            openai_file = client.files.create(file=(file_name, file_bytes), purpose="assistants")
            attachments = [{"file_id": openai_file.id, "tools": [{"type": "file_search"}, {"type": "code_interpreter"}]}]
            
            message_content = user_input if user_input else "이 파일을 분석해주세요."
            display_input = f"📄 **[첨부파일: {file_name}]**\n\n{user_input}"

    # 5-2. 사용자 메시지 즉시 화면에 추가
    st.session_state.messages.append({"role": "user", "text": display_input})
    with st.chat_message("user"):
        st.markdown(display_input)
        
    # 5-3. AI 응답 처리 (스피너 로딩 화면 제공)
    with st.chat_message("assistant"):
        with st.spinner("AI가 답변을 생각하고 있습니다... (데이터 분석 시 시간이 소요될 수 있습니다)"):
            
            # 스레드에 메시지 전송
            client.beta.threads.messages.create(
                thread_id=st.session_state.thread_id,
                role="user",
                content=message_content, 
                attachments=attachments if attachments else None
            )
            
            # Run 생성 및 상태 확인
            run = client.beta.threads.runs.create(
                thread_id=st.session_state.thread_id,
                assistant_id=assistant.id
            )
            
            while run.status in ['queued', 'in_progress', 'cancelling']:
                time.sleep(1)
                run = client.beta.threads.runs.retrieve(thread_id=st.session_state.thread_id, run_id=run.id)
                
                # 함수 호출 (날씨, 계산) 처리
                if run.status == 'requires_action':
                    tool_outputs = []
                    for tool_call in run.required_action.submit_tool_outputs.tool_calls:
                        args = json.loads(tool_call.function.arguments)
                        if tool_call.function.name == "multiply_numbers":
                            res = multiply_numbers(a=args.get("a"), b=args.get("b"))
                            tool_outputs.append({"tool_call_id": tool_call.id, "output": str(res)})
                        elif tool_call.function.name == "get_weather":
                            res = get_weather(location=args.get("location"))
                            tool_outputs.append({"tool_call_id": tool_call.id, "output": str(res)})
                            
                    if tool_outputs:
                        run = client.beta.threads.runs.submit_tool_outputs(
                            thread_id=st.session_state.thread_id, run_id=run.id, tool_outputs=tool_outputs
                        )

            # 5-4. 결과 파싱 및 화면 출력
            if run.status == 'completed':
                messages = client.beta.threads.messages.list(thread_id=st.session_state.thread_id)
                latest_message = messages.data[0]
                
                response_text = ""
                image_data_list = [] # 바이너리 이미지 데이터 리스트
                
                for content_block in latest_message.content:
                    if content_block.type == 'text':
                        text_value = content_block.text.value
                        if hasattr(content_block.text, 'annotations'):
                            for annotation in content_block.text.annotations:
                                text_value = text_value.replace(annotation.text, "")
                        response_text += text_value + "\n"
                        
                    elif content_block.type == 'image_file':
                        # 생성된 이미지(그래프 등) 바이너리 추출
                        file_id = content_block.image_file.file_id
                        image_bytes = client.files.content(file_id).read()
                        image_data_list.append(image_bytes)
                
                # 현재 화면에 출력
                if response_text.strip():
                    st.markdown(response_text.strip())
                for img_bytes in image_data_list:
                    st.image(img_bytes)
                    
                # 다음 새로고침을 위해 세션 상태에 저장
                st.session_state.messages.append({
                    "role": "assistant", 
                    "text": response_text.strip(), 
                    "images": image_data_list
                })
            else:
                error_msg = f"⚠️ 오류 발생: {run.status}"
                st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "text": error_msg})
