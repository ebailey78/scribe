import soundcard as sc
import sys

with open("devices.txt", "w", encoding="utf-8") as f:
    sys.stdout = f
    
    print("Listing all microphones (including loopback):")
    try:
        mics = sc.all_microphones(include_loopback=True)
        for i, mic in enumerate(mics):
            print(f"[{i}] {mic.name} (Loopback: {mic.isloopback})")

        print("\nDefault Speaker:")
        default_speaker = sc.default_speaker()
        print(f"Name: {default_speaker.name}")

        print("\nTesting find_default_loopback logic:")
        found = False
        for idx, mic in enumerate(mics):
            if mic.isloopback and default_speaker.name in mic.name:
                print(f"MATCH FOUND: [{idx}] {mic.name}")
                found = True
                break
        
        if not found:
            print("NO MATCH FOUND for default loopback.")

    except Exception as e:
        print(f"Error: {e}")
