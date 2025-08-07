import modal
import json
from pathlib import Path
from io import BytesIO

def download_models():
    from diffusers import AutoPipelineForImage2Image, LCMScheduler
    import torch

    pipeline = AutoPipelineForImage2Image.from_pretrained(
        "Lykon/dreamshaper-8",
        torch_dtype=torch.float16,
        safety_checker=None,
        variant="fp16",
    )

    pipeline.scheduler = LCMScheduler.from_config(pipeline.scheduler.config)
    pipeline.load_lora_weights("latent-consistency/lcm-lora-sdv1-5", adapter_name="lcm")


app = modal.App("websocket-image-server")
app.image = (
    modal.Image.debian_slim()
    .pip_install("fastapi", "websockets", "python-multipart")
    .pip_install(
        "python-multipart",
        "torch",
        "uvicorn",
        "transformers",
        "websockets",
        "peft",
        "accelerate",
        "torchvision",
        "datasets",
        "ftfy",
        "diffusers[torch]",
        "opencv-python",
        "DeepCache",
        "huggingface-hub",
    )
    .apt_install("curl")
    .add_local_dir(
        Path(__file__).parent / "app",
        "/root/app",
        copy=True,
    )
        .run_commands(
        "mkdir -p /root/models",
        "curl -L https://realtime-public-assets.s3.us-west-2.amazonaws.com/lora/hairy-cute.safetensors -o /root/models/hairy-cute.safetensors",
    )
    .run_function(download_models)
)
# Store user settings and connections
users = {}

def calculate_params(
    ai_strength,
    strength_min=0.13,
    strength_max=1.0,
    guidance_scale_min=0.1,
    guidance_scale_max=2.0,
):
    ai_strength_normalized = ai_strength / 100.0
    strength = strength_min + ai_strength_normalized * (strength_max - strength_min)
    guidance_scale = guidance_scale_min + ai_strength_normalized * (
        guidance_scale_max - guidance_scale_min
    )
    return strength, guidance_scale

@app.function(
    max_containers=2,
    gpu="a10g",
)
@modal.concurrent(max_inputs=1000)
@modal.asgi_app()
def endpoint():
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse
    from DeepCache import DeepCacheSDHelper
    from diffusers import AutoPipelineForImage2Image, LCMScheduler
    import torch
    from PIL import Image

    print("Loading pipeline")
    # Load pipeline
    pipeline = AutoPipelineForImage2Image.from_pretrained(
        "Lykon/dreamshaper-8",
        torch_dtype=torch.float16,
        safety_checker=None,
        variant="fp16",
    ).to("cuda")

    pipeline.scheduler = LCMScheduler.from_config(
        pipeline.scheduler.config
    )
    print("Loading LCM LoRA")
    pipeline.load_lora_weights(
        "latent-consistency/lcm-lora-sdv1-5", adapter_name="lcm"
    )

    # Setup DeepCacheSDHelper
    helper = DeepCacheSDHelper(pipe=pipeline)
    helper.set_params(
        cache_interval=1,
        cache_branch_id=0,
    )
    helper.enable()

    print("Fusing QKV projections")
    pipeline.fuse_qkv_projections()

    # Load LoRA weights
    print("Loading LoRA weights")
    pipeline.load_lora_weights(
        "models/hairy-cute.safetensors", adapter_name="hairy-cute"
    )
    print("LoRA weights loaded successfully")

    adapters = ["lcm", "hairy-cute"]

    app = FastAPI()

    app.mount("/css", StaticFiles(directory="app/css"), name="css")
    app.mount("/resources", StaticFiles(directory="app/resources"), name="resources")
    app.mount("/worker", StaticFiles(directory="app/worker"), name="worker")

    # Serve JS files from app root
    @app.get("/sculptgl.js")
    async def get_js():
        return FileResponse("app/sculptgl.js")

    @app.get("/sculptgl.js.LICENSE.txt")
    async def get_license():
        return FileResponse("app/sculptgl.js.LICENSE.txt")

    # Serve HTML files
    @app.get("/")
    async def root():
        return FileResponse("app/index.html")

    @app.get("/authSuccess.html")
    async def auth_success():
        return FileResponse("app/authSuccess.html")

    @app.websocket("/ws")
    async def websocket_handler(websocket: WebSocket) -> None:
        # Extract user_id from query params
        query_params = dict(websocket.query_params)
        user_id = query_params.get("userid")

        if not user_id:
            await websocket.close(code=1000, reason="Missing userid parameter")
            return

        await websocket.accept()
        users[user_id] = {"websocket": websocket, "settings": None}

        try:
            while True:
                try:
                    # Receive message (could be text or bytes)
                    message = await websocket.receive()
                except Exception as e:
                    # Handle any receive errors (including disconnect)
                    print(f"WebSocket receive error for user {user_id}: {e}")
                    break

                if "text" in message and message["text"] is not None:  # JSON settings
                    try:
                        settings = json.loads(message["text"])
                        if all(
                            key in settings for key in ["style", "strength", "seed", "prompt"]
                        ):
                            users[user_id]["settings"] = settings
                            try:
                                await websocket.send_json({"status": "settings_saved"})
                            except Exception as e:
                                print(f"Error sending settings confirmation: {e}")
                                break
                        else:
                            try:
                                await websocket.send_json(
                                    {
                                        "error": "Missing required fields: style, strength, seed, prompt"
                                    }
                                )
                            except Exception as e:
                                print(f"Error sending error message: {e}")
                                break
                    except json.JSONDecodeError:
                        try:
                            await websocket.send_json({"error": "Invalid JSON"})
                        except Exception as e:
                            print(f"Error sending JSON decode error: {e}")
                            break

                elif (
                    "bytes" in message and message["bytes"] is not None
                ):  # Binary image
                    if users[user_id]["settings"] is None:
                        try:
                            await websocket.send_json({"error": "Send JSON settings first"})
                        except Exception as e:
                            print(f"Error sending settings error: {e}")
                            break
                    else:
                        print("Processing image for user", user_id, "with settings", users[user_id]['settings'])
                        settings = users[user_id]['settings']

                        if settings['style'] == 'hairy-cute':
                            weights = [1.0, 0.8]
                            settings['prompt'] += 'j_hairy'
                        else:
                            weights = [1.0, 1.0]

                        pipeline.set_adapters(adapters, adapter_weights=weights)
                        generator = torch.manual_seed(settings['seed'])
                        strength, guidance = calculate_params(settings['strength'])

                        # Convert bytes to PIL Image
                        input_image = Image.open(BytesIO(message["bytes"]))

                        generated_image = pipeline(
                            settings['prompt'],
                            image=input_image,
                            strength=strength,
                            guidance_scale=guidance,
                            negative_prompt="nsfw, watermark, monochrome, lowres, bad anatomy, worst quality, low quality",
                            num_inference_steps=8,
                            num_images_per_prompt=1,
                            height=512,
                            width=512,
                            generator=generator,
                        ).images[0]

                        # Save image to bytes
                        byte_stream = BytesIO()
                        generated_image.save(byte_stream, format="JPEG")
                        byte_stream.seek(0)

                        try:
                            await websocket.send_bytes(byte_stream.getvalue())
                            print("Image sent to user", user_id)
                        except Exception as e:
                            print(f"Error sending image to user {user_id}: {e}")
                            break

        except WebSocketDisconnect:
            pass
        finally:
            # Clean up user data
            if user_id in users:
                del users[user_id]

    return app
