import logging
import config

# --- UNIFIED ENTRY POINT ---
def main():
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )
    
    print(f"--- Starting in {config.RUN_MODE} Mode ---")
    
    if config.RUN_MODE == "CLIENT":
        import client_mode
        client_mode.run()
    else:
        import bot_mode
        bot_mode.run()

if __name__ == "__main__":
    main()
