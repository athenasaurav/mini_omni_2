"""
FastAPI server for Mini-Omni-2

Run with:
  uvicorn server_fast:app --host 0.0.0.0 --port 60808 --workers 1 --http h2

(You can omit --http h2 if you don't need HTTP/2, but it's recommended for streaming.)
"""
import os
import base64
import tempfile
import traceback
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from inference_vision import OmniVisionInference
import asyncio

app = FastAPI()

# Load model at startup
ckpt_dir = './checkpoint'
device = 'cuda:0'
client = OmniVisionInference(ckpt_dir, device)
client.warm_up()

@app.post("/chat")
async def chat(request: Request):
    try:
        req_data = await request.json()
        audio_data_buf = req_data["audio"].encode("utf-8")
        audio_data_buf = base64.b64decode(audio_data_buf)
        stream_stride = req_data.get("stream_stride", 4)
        max_tokens = req_data.get("max_tokens", 2048)

        image_data_buf = req_data.get("image", None)
        if image_data_buf:
            image_data_buf = image_data_buf.encode("utf-8")
            image_data_buf = base64.b64decode(image_data_buf)

        audio_path, img_path = None, None
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as audio_f, \
             tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as img_f:
            audio_f.write(audio_data_buf)
            audio_path = audio_f.name

            if image_data_buf:
                img_f.write(image_data_buf)
                img_path = img_f.name
            else:
                img_path = None

            if img_path is not None:
                resp_generator = client.run_vision_AA_batch_stream(audio_f.name, img_f.name,
                                                                   stream_stride, max_tokens,
                                                                   save_path='./vision_qa_out_cache.wav')
            else:
                resp_generator = client.run_AT_batch_stream(audio_f.name, stream_stride,
                                                            max_tokens,
                                                            save_path='./audio_qa_out_cache.wav')

            async def streamer():
                loop = asyncio.get_event_loop()
                for audio_stream, text_stream in resp_generator:
                    yield b'\r\n--frame\r\n'
                    yield b'Content-Type: audio/wav\r\n\r\n'
                    yield audio_stream
                    yield b'\r\n--frame\r\n'
                    yield b'Content-Type: text/plain\r\n\r\n'
                    yield text_stream.encode()
                    await asyncio.sleep(0)  # Yield control to event loop

            return StreamingResponse(streamer(), media_type='multipart/x-mixed-replace; boundary=frame')
    except Exception as e:
        print(traceback.format_exc())
        return StreamingResponse((b"An error occurred",), media_type="text/plain", status_code=500) 