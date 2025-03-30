import React, { useState, useEffect, useCallback } from 'react';
import { apiService } from '../services/api';
import { TaskType, TaskResponse, ModelCapability } from '../types';

interface TaskManagerProps {
  onTaskComplete: (response: TaskResponse) => void;
  onError: (error: string) => void;
  code: string;
}

export const TaskManager: React.FC<TaskManagerProps> = ({ onTaskComplete, onError, code }) => {
  const [capabilities, setCapabilities] = useState<Record<string, ModelCapability>>({});
  const [activeTask, setActiveTask] = useState<TaskType | null>(null);
  const [taskHistory, setTaskHistory] = useState<TaskResponse[]>([]);

  const loadCapabilities = useCallback(async () => {
    try {
      const caps = await apiService.getModelCapabilities();
      setCapabilities(caps);
    } catch (error) {
      onError('Failed to load model capabilities');
    }
  }, [onError]);

  const loadTaskHistory = useCallback(async () => {
    try {
      const history = await apiService.getTaskHistory(5);
      setTaskHistory(history);
    } catch (error) {
      onError('Failed to load task history');
    }
  }, [onError]);

  useEffect(() => {
    loadCapabilities();
    loadTaskHistory();
  }, [loadCapabilities, loadTaskHistory]);

  const executeTask = async (taskType: TaskType) => {
    if (!code.trim()) {
      onError('Please enter some code first');
      return;
    }

    setActiveTask(taskType);
    try {
      const response = await apiService.executeTask(taskType, code);
      setTaskHistory(prev => [response, ...prev]);
      onTaskComplete(response);
    } catch (error) {
      onError(error instanceof Error ? error.message : 'Task execution failed');
    } finally {
      setActiveTask(null);
    }
  };

  const getTaskButtonStyle = (taskType: TaskType) => {
    const baseStyle = "px-4 py-2 rounded-lg shadow-glow transition-all duration-200";
    const activeStyle = activeTask === taskType ? "opacity-50 cursor-not-allowed" : "";
    const disabledStyle = !code.trim() ? "opacity-50 cursor-not-allowed" : "";
    
    switch (taskType) {
      case 'explain':
        return `${baseStyle} bg-blue-700 hover:bg-blue-500 ${activeStyle} ${disabledStyle}`;
      case 'fix_bugs':
        return `${baseStyle} bg-yellow-600 hover:bg-yellow-400 ${activeStyle} ${disabledStyle}`;
      case 'generate_tests':
        return `${baseStyle} bg-green-700 hover:bg-green-500 ${activeStyle} ${disabledStyle}`;
      case 'document':
        return `${baseStyle} bg-purple-700 hover:bg-purple-500 ${activeStyle} ${disabledStyle}`;
      case 'optimize':
        return `${baseStyle} bg-red-700 hover:bg-red-500 ${activeStyle} ${disabledStyle}`;
      default:
        return baseStyle;
    }
  };

  return (
    <div className="w-full max-w-2xl mx-auto">
      <div className="flex flex-wrap gap-4 mb-6">
        {Object.entries(capabilities).map(([model, capability]) => (
          capability.supported_tasks.map(taskType => (
            <button
              key={`${model}-${taskType}`}
              onClick={() => executeTask(taskType)}
              disabled={activeTask !== null || !code.trim()}
              className={getTaskButtonStyle(taskType)}
            >
              {taskType.replace('_', ' ').toUpperCase()}
            </button>
          ))
        ))}
      </div>
      
      {taskHistory.length > 0 && (
        <div className="mt-4 p-4 bg-zinc-800 rounded-lg border border-cyan-700">
          <h3 className="text-cyan-300 mb-2">Recent Tasks</h3>
          <div className="space-y-2">
            {taskHistory.map((task, index) => (
              <div key={task.task_id || index} className="text-sm text-cyan-200">
                <span className="font-bold">{task.task_type}:</span> {task.response.substring(0, 50)}...
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}; 