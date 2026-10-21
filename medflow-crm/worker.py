import time

from whatsapp import process_queue

if __name__ == "__main__":
    print("MedFlow WhatsApp worker запущен. Для остановки нажмите Ctrl+C.")
    while True:
        processed = process_queue()
        if processed:
            print(f"Обработано сообщений: {processed}")
        time.sleep(15)

