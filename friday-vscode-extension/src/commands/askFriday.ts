import * as vscode from 'vscode';
import fetch from 'node-fetch';

export async function askFriday() {
  const editor = vscode.window.activeTextEditor;
  if (!editor) {
    vscode.window.showErrorMessage("No active editor found.");
    return;
  }

  const text = editor.document.getText();
  const input = await vscode.window.showInputBox({ prompt: "Ask FRIDAY anything about this file:" });
  if (!input) return;

  try {
    const response = await fetch('http://localhost:8001/process', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ input, file: text }),
    });

    const data = await response.json();
    vscode.window.showInformationMessage(data.response || "FRIDAY returned no answer.");
  } catch (err) {
    vscode.window.showErrorMessage("Failed to contact FRIDAY backend.");
  }
}
