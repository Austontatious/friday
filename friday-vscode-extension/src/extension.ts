import * as vscode from 'vscode';
import { askFriday } from './commands/askFriday';

export function activate(context: vscode.ExtensionContext) {
  console.log('FRIDAY extension is now active!');

  let disposable = vscode.commands.registerCommand('friday.askAnything', askFriday);
  context.subscriptions.push(disposable);
}

export function deactivate() {}
