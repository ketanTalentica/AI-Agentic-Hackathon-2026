import os

class CommonLogger:
    @staticmethod
    def WriteLog(log_path, message):
        """
        Appends the message to the log file at log_path, creating the file if it does not exist.
        Args:
            log_path (str): Relative or absolute path to the log file.
            message (str): The message to write (will append a newline).
        """
        try:
            # Debugging: Print log path and message
            print(f"[DEBUG] Writing to log file: {log_path}")
            print(f"[DEBUG] Message: {message}")

            # Ensure the directory exists
            log_dir = os.path.dirname(log_path)
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)

            with open(log_path, "a", encoding="utf-8") as f:
                f.write(message + "\n")
        except Exception as e:
            print(f"[ERROR] Failed to write to log file: {e}")
