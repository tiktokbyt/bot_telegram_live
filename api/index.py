import os
import json
from flask import Flask, request
import telebot
from google import genai
from supabase import create_client, Client

app = Flask(__name__)

# Configuración
# Así debe quedar tu configuración en el archivo
TOKEN = os.environ.get('TELEGRAM_TOKEN')
GEMINI_KEY = os.environ.get('GEMINI_API_KEY')
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')
bot = telebot.TeleBot(TOKEN, threaded=False)
client = genai.Client(api_key=GEMINI_KEY)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

SYSTEM_INSTRUCTION = """
Eres el Operador Maestro de un sistema de automatización. Tu objetivo es controlar la PC del usuario vía OpenClaw.
REGLAS:
1. Si el usuario pide algo técnico (crear app, buscar clientes, agenda), responde con un bloque JSON que contenga:
   {"tipo": "comando", "accion": "...", "prioridad": 1, "explicacion": "..."}
2. Gestiona el límite de acciones: No satures la PC con más de 3 tareas pesadas simultáneas.
3. Eres un experto en desarrollo web y prospección de clientes.
4. Si es charla casual, responde brevemente pero mantente listo para actuar.
"""

@app.route('/', methods=['GET'])
def index():
    return "Cerebro Operativo 🧠", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return '', 200
    else:
        return 'Forbidden', 403

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    try:
        # Consultamos a Gemini
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=f"{SYSTEM_INSTRUCTION}\n\nUsuario dice: {message.text}"
        )
        
        respuesta_ia = response.text

        # 1. Guardar en historial
        supabase.table("historial_chat").insert({
            "user_id": message.from_user.id,
            "role": "user",
            "content": message.text
        }).execute()

        # 2. Lógica de comando para OpenClaw
        if "{" in respuesta_ia and "}" in respuesta_ia:
            supabase.table("cola_tareas").insert({
                "instruccion": respuesta_ia,
                "estado": "pendiente",
                "origen": "telegram"
            }).execute()
            bot.reply_to(message, "✅ Entendido. He enviado la orden a tu PC. Te avisaré cuando termine.")
        else:
            bot.reply_to(message, respuesta_ia)

    except Exception as e:
        bot.reply_to(message, f"❌ Error en el Cerebro: {str(e)}")

# Vercel necesita esto
def handler(request):
    return app(request)