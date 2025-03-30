import { TaskType, TaskResponse } from '../types';

class ApiService {
  private baseUrl: string;
  private port: string | null = null;
  private portDiscoveryAttempts = 0;
  private readonly MAX_PORT_DISCOVERY_ATTEMPTS = 5;
  private readonly PORT_DISCOVERY_INTERVAL = 2000; // 2 seconds
  private readonly PORT_RANGE = {
    start: 8001,
    end: 8100
  };

  constructor() {
    this.baseUrl = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';
    this.initializeBaseUrl();
  }

  private async initializeBaseUrl() {
    try {
      // First try to get port from environment variable
      const envPort = process.env.REACT_APP_BACKEND_PORT;
      if (envPort) {
        this.port = envPort;
        this.baseUrl = this.getBackendUrl();
        console.log('Using environment port:', this.port);
        await this.verifyBackendConnection();
        return;
      }

      // Try to discover backend port
      await this.discoverBackendPort();
    } catch (error) {
      console.error('Failed to initialize backend connection:', error);
      throw error;
    }
  }

  private async discoverBackendPort(): Promise<void> {
    let currentPort = this.PORT_RANGE.start;

    while (this.portDiscoveryAttempts < this.MAX_PORT_DISCOVERY_ATTEMPTS) {
      try {
        // Try current port
        this.port = currentPort.toString();
        this.baseUrl = this.getBackendUrl();
        console.log('Trying backend port:', this.port);

        // Verify connection
        await this.verifyBackendConnection();
        console.log('Successfully connected to backend on port:', this.port);
        return;

      } catch (error) {
        console.log(`Failed to connect on port ${currentPort}:`, error);
        currentPort++;
        
        if (currentPort > this.PORT_RANGE.end) {
          currentPort = this.PORT_RANGE.start;
          this.portDiscoveryAttempts++;
          
          if (this.portDiscoveryAttempts >= this.MAX_PORT_DISCOVERY_ATTEMPTS) {
            const errorMessage = 'Backend server not found. Please ensure the backend is running and try again.';
            console.error(errorMessage);
            throw new Error(errorMessage);
          }
          
          // Wait before next attempt
          await new Promise(resolve => setTimeout(resolve, this.PORT_DISCOVERY_INTERVAL));
        }
      }
    }
  }

  private async verifyBackendConnection(): Promise<void> {
    try {
      const response = await fetch(`${this.baseUrl}/models/capabilities`, {
        method: 'GET',
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json'
        },
        credentials: 'include'  // Include credentials for CORS
      });
      
      if (!response.ok) {
        throw new Error(`Backend server not responding (status: ${response.status})`);
      }
      
      // Verify we got valid JSON response
      const data = await response.json();
      if (!data || typeof data !== 'object') {
        throw new Error('Invalid response from backend');
      }
      
    } catch (error) {
      if (error instanceof TypeError && error.message.includes('Failed to fetch')) {
        throw new Error('Backend server not running. Please start the backend server first.');
      }
      throw error;
    }
  }

  private getBackendUrl(): string {
    if (!this.port) {
      throw new Error('Backend port not initialized');
    }
    // Use localhost instead of window.location.origin for backend connection
    const url = `http://localhost:${this.port}`;
    console.log('Backend URL:', url);
    return url;
  }

  private async handleResponse(response: Response): Promise<any> {
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
    }
    return response.json();
  }

  async processInput(input: string): Promise<TaskResponse> {
    console.log('Processing input:', input);
    try {
      const response = await fetch(`${this.baseUrl}/process`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        body: JSON.stringify({ input }),
      });
      
      const data = await this.handleResponse(response);
      
      // Validate response structure
      if (!data || typeof data !== 'object') {
        throw new Error('Invalid response format');
      }
      
      return {
        task_id: data.task_id,
        response: data.output,
        status: data.status,
        error: data.error,
        task_type: data.task_type,
        metadata: data.details
      };
    } catch (error) {
      console.error('Error processing input:', error);
      throw error;
    }
  }

  async executeTask(taskType: TaskType, code: string): Promise<TaskResponse> {
    console.log('Executing task:', taskType, 'with code length:', code.length);
    const response = await fetch(`${this.baseUrl}/process/${taskType}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code }),
    });
    return this.handleResponse(response);
  }

  async getTaskStatus(taskId: string): Promise<TaskResponse> {
    console.log('Getting task status for:', taskId);
    const response = await fetch(`${this.baseUrl}/tasks/${taskId}`);
    return this.handleResponse(response);
  }

  async getTaskHistory(limit: number = 10): Promise<TaskResponse[]> {
    console.log('Getting task history, limit:', limit);
    const response = await fetch(`${this.baseUrl}/tasks/history?limit=${limit}`);
    return this.handleResponse(response);
  }

  async getModelCapabilities(): Promise<Record<string, any>> {
    console.log('Getting model capabilities');
    const response = await fetch(`${this.baseUrl}/models/capabilities`);
    return this.handleResponse(response);
  }
}

export const apiService = new ApiService(); 