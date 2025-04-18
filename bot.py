import os
import stripe
from telegram import Update, LabeledPrice
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    PreCheckoutQueryHandler, ContextTypes, filters
)
from PyPDF2 import PdfReader
from email.message import EmailMessage
import smtplib

# Load environment variables
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_PROVIDER_TOKEN = os.getenv("STRIPE_PROVIDER_TOKEN")
PRINTER_EMAIL = os.getenv("PRINTER_EMAIL")
SMTP_EMAIL = os.getenv("SMTP_EMAIL")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")

stripe.api_key = STRIPE_SECRET_KEY

def send_to_printer(file_path, printer_email):
    msg = EmailMessage()
    msg["Subject"] = "Print Job"
    msg["From"] = SMTP_EMAIL
    msg["To"] = printer_email

    with open(file_path, "rb") as f:
        msg.add_attachment(
            f.read(), maintype="application", subtype="pdf", filename=os.path.basename(file_path)
        )

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(SMTP_EMAIL, SMTP_PASSWORD)
        smtp.send_message(msg)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send me a PDF document to print. It's €1 per page.")

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = update.message.document
    file_obj = await file.get_file()
    file_path = f"downloads/{file.file_id}.pdf"
    os.makedirs("downloads", exist_ok=True)
    await file_obj.download_to_drive(file_path)

    reader = PdfReader(file_path)
    page_count = len(reader.pages)
    price_cents = page_count * 100  # €1 per page

    context.user_data["file_path"] = file_path
    context.user_data["page_count"] = page_count

    prices = [LabeledPrice(f"{page_count} page(s)", price_cents)]
    await update.message.reply_invoice(
        title="Print Job",
        description=f"Printing {page_count} page(s)",
        payload="print_payload_001",
        provider_token=STRIPE_PROVIDER_TOKEN,
        currency="EUR",
        prices=prices
    )

async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    await query.answer(ok=True)

async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file_path = context.user_data.get("file_path")
    if file_path:
        send_to_printer(file_path, PRINTER_EMAIL)
        await update.message.reply_text("Payment received! Your file is printing now.")
    else:
        await update.message.reply_text("Payment received, but no file found.")

if __name__ == "__main__":
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.PDF, handle_file))
    app.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))
    app.run_polling()
