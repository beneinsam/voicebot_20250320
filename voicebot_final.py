import streamlit as st
import openai
import os
from dotenv import load_dotenv
from audiorecorder import audiorecorder
from datetime import datetime
import base64
import requests
import json

load_dotenv()

client = openai.OpenAI()

def get_weather(location):
    """Function to get weather information for a given location"""
    response = requests.get(f"https://api.open-meteo.com/v1/forecast?latitude=37.5665&longitude=126.9780&current_weather=true")
    if response.status_code == 200:
        data = response.json()
        return f"현재 {location}의 온도는 {data['current_weather']['temperature']}°C 입니다."
    return "날씨 정보를 가져오는 데 실패했습니다."

def get_exchange_rate():
    """Function to get the current USD to KRW exchange rate"""
    response = requests.get("https://api.exchangerate-api.com/v4/latest/USD")
    if response.status_code == 200:
        data = response.json()
        rate = data['rates'].get('KRW', '알 수 없음')
        return f"현재 원-달러 환율은 1달러당 {rate}원 입니다."
    return "환율 정보를 가져오는 데 실패했습니다."

def speech_to_text(speech):
    filename='input.mp3'
    speech.export(filename, format="mp3")
    
    with open(filename, "rb") as audio_file:
        transcription = client.audio.transcriptions.create(
            model="whisper-1", 
            file=audio_file
        )
    os.remove(filename)
    return transcription.text

tools = [{
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "서울의 현재 날씨를 조회합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {"type": "string"}
            },
            "required": ["location"],
            "additionalProperties": False
        },
        "strict": True
    }
}, {
    "type": "function",
    "function": {
        "name": "get_exchange_rate",
        "description": "원화 기준 달러의 현재 환율을 조회합니다.",
        "parameters": {
            "type": "object",
            "properties": {},
            "additionalProperties": False
        },
        "strict": True
    }
}]

def generate_chat_response(messages):
    response = client.chat.completions.create(
        model="gpt-4o-mini", 
        messages=messages,
        tools=tools,
        tool_choice="auto"
    )
    
    tool_calls = response.choices[0].message.tool_calls

    if tool_calls:
        messages.append({
            "role": "assistant",
            "tool_calls": tool_calls
        })

        for tool_call in tool_calls:
            func_name = tool_call.function.name
            func_args = json.loads(tool_call.function.arguments)

            if func_name == "get_weather":
                result = get_weather(func_args["location"])
            elif func_name == "get_exchange_rate":
                result = get_exchange_rate()
            else:
                result = "기능을 찾을 수 없습니다."

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": str(result)
            })

        final_response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            tools=tools,
            #tool_choice="auto"
        )
        return final_response.choices[0].message.content
    else:
        return response.choices[0].message.content

def text_to_speech(text):
    filename = "output.mp3"
    response = client.audio.speech.create(
        model="tts-1",
        #voice="alloy",
        voice="fable",
        input=text,
        speed=0.9,
    )    
    with open(filename, "wb") as f:
        f.write(response.content)

    with open(filename, "rb") as f:
        data = f.read()
        b64 = base64.b64encode(data).decode()
        md = f"""
            <audio autoplay="True">
            <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
            </audio>
            """
        st.markdown(md, unsafe_allow_html=True)
    os.remove(filename)

def main():
    st.set_page_config(page_title="🎤 음성 챗봇 서비스", layout="wide")
    st.header("🎤 음성 챗봇 서비스 by 박상종종")
    st.markdown("---")

    with st.expander("🎤 음성 챗봇 서비스에 대하여", expanded=True):
        st.write(
            """     
            - 음성 챗봇 서비스는 Streamlit UI를 사용합니다.
            - STT(Speech-To-Text)는 OpenAI의 Whisper를 사용합니다. 
            - 답변은 OpenAI의 GPT 모델을 사용합니다. 
            - TTS(Text-To-Speech)는 OpenAI의 TTS을 사용합니다.
            - 도시는 서울로 고정되어 있고, 환율은 KRW 기준으로 USD 환율을 조회합니다.
            """
        )

    system_message = "당신은 친절한 도우미입니다. 30 단어 미만의 한국어로 답변해 주세요."

    if "chat" not in st.session_state:
        st.session_state["chat"] = []

    if "messages" not in st.session_state:
        st.session_state["messages"] = [{"role": "system", "content": system_message}]

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("음성 전송")
        audio = audiorecorder()
        if (audio.duration_seconds > 0):
            st.audio(audio.export().read())
            question = speech_to_text(audio)
            now = datetime.now().strftime("%H:%M")
            st.session_state["chat"].append(("user", now, question))
            st.session_state["messages"].append({"role": "user", "content": question})

    with col2:
        st.subheader("대화 내역")
        if audio.duration_seconds > 0:
            response_content = generate_chat_response(st.session_state["messages"])
            st.session_state["messages"].append({"role": "assistant", "content": response_content})
            now = datetime.now().strftime("%H:%M")
            st.session_state["chat"].append(("bot", now, response_content))
            for sender, time, message in st.session_state["chat"]:
                if sender == "user":
                    st.write(f'<div style="display:flex;align-items:center;"><div style="background-color:#007AFF;color:white;border-radius:12px;padding:8px 12px;margin-right:8px;">{message}</div><div style="font-size:0.8rem;color:gray;">{time}</div></div>', unsafe_allow_html=True)
                else:
                    st.write(f'<div style="display:flex;align-items:center;justify-content:flex-end;"><div style="background-color:lightgray;border-radius:12px;padding:8px 12px;margin-left:8px;">{message}</div><div style="font-size:0.8rem;color:gray;">{time}</div></div>', unsafe_allow_html=True)
            text_to_speech(response_content)

if __name__ == "__main__":
    main()
