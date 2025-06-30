# --- DOSYA: generate_keys.py ---
import secrets

def generate_keys(count=100):
    keys = [secrets.token_urlsafe(24) for _ in range(count)]
    with open("keys.txt", "w") as f:
        for key in keys:
            f.write(f"{key}\n")
    print(f"{count} adet yeni anahtar 'keys.txt' dosyasına yazıldı.")

if __name__ == '__main__':
    generate_keys()
