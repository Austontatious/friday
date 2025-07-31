import time
from statistics import mean

class AffectTracker:
    def __init__(self, window_size=20):
        self.loss_window = []
        self.window_size = window_size
        self.last_emotion = None

    def update(self, current_loss: float):
        self.loss_window.append(current_loss)
        if len(self.loss_window) > self.window_size:
            self.loss_window.pop(0)

        # Compute trends
        avg_loss = mean(self.loss_window)
        delta = current_loss - avg_loss

        emotion = self.infer_emotion(delta)
        self.last_emotion = emotion
        self.log_emotion(emotion, current_loss, avg_loss, delta)
        return emotion

    def infer_emotion(self, delta):
        if delta < -0.05:
            return "joy"
        elif delta < -0.01:
            return "content"
        elif abs(delta) <= 0.01:
            return "neutral"
        elif delta <= 0.05:
            return "concern"
        else:
            return "frustration"

    def log_emotion(self, emotion, current_loss, avg_loss, delta):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_line = (
            f"[{timestamp}] Emotion: {emotion.upper():<12} | "
            f"Loss: {current_loss:.5f} | "
            f"AvgLoss: {avg_loss:.5f} | Δ: {delta:.5f}"
        )
        with open("logs/friday_affect.log", "a") as f:
            f.write(log_line + "\n")

