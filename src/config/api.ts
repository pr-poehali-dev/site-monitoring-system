export const API_BASE_URL = 'https://functions.poehali.dev/0d1dbd15-7762-4fb3-af49-47c960f9828b';
export const PARSER_BASE_URL = 'https://functions.poehali.dev/8c4db4b8-687e-471b-add5-e4517d47764c';

export const apiClient = {
  async getDocuments(params?: { 
    search?: string; 
    section?: string; 
    year?: string;
    sort_by?: string;
    sort_order?: string;
    limit?: number; 
    offset?: number 
  }) {
    const queryParams = new URLSearchParams({
      endpoint: 'documents',
      ...params
    } as Record<string, string>);
    
    const response = await fetch(`${API_BASE_URL}?${queryParams}`);
    if (!response.ok) throw new Error('Failed to fetch documents');
    return response.json();
  },

  async getChanges(limit?: number, documentId?: number) {
    const queryParams = new URLSearchParams({
      endpoint: 'changes',
      ...(limit && { limit: limit.toString() }),
      ...(documentId && { document_id: documentId.toString() })
    });
    
    const response = await fetch(`${API_BASE_URL}?${queryParams}`);
    if (!response.ok) throw new Error('Failed to fetch changes');
    return response.json();
  },

  async getLogs(limit?: number) {
    const queryParams = new URLSearchParams({
      endpoint: 'logs',
      ...(limit && { limit: limit.toString() })
    });
    
    const response = await fetch(`${API_BASE_URL}?${queryParams}`);
    if (!response.ok) throw new Error('Failed to fetch logs');
    return response.json();
  },

  async getSettings() {
    const queryParams = new URLSearchParams({ endpoint: 'settings' });
    
    const response = await fetch(`${API_BASE_URL}?${queryParams}`);
    if (!response.ok) throw new Error('Failed to fetch settings');
    return response.json();
  },

  async getStats() {
    const queryParams = new URLSearchParams({ endpoint: 'stats' });
    
    const response = await fetch(`${API_BASE_URL}?${queryParams}`);
    if (!response.ok) throw new Error('Failed to fetch stats');
    return response.json();
  },

  async updateSettings(settings: Record<string, any>) {
    const queryParams = new URLSearchParams({ endpoint: 'settings' });
    
    const response = await fetch(`${API_BASE_URL}?${queryParams}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(settings)
    });
    
    if (!response.ok) throw new Error('Failed to update settings');
    return response.json();
  },

  async runParser(sections: string[], years: number[], force: boolean = false) {
    fetch(PARSER_BASE_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        action: 'parse',
        sections,
        years,
        force
      })
    }).catch(() => {});
    
    return { status: 'started' };
  },

  async runMonitor() {
    const response = await fetch(PARSER_BASE_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        action: 'monitor'
      })
    });
    
    if (!response.ok) throw new Error('Failed to run monitor');
    return response.json();
  },

  async continueParsing(autoLoop: boolean = false) {
    const response = await fetch(PARSER_BASE_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        action: 'continue_parsing',
        auto_loop: autoLoop
      })
    });
    
    if (!response.ok) throw new Error('Failed to continue parsing');
    return response.json();
  },

  async getParsingProgress() {
    const queryParams = new URLSearchParams({ endpoint: 'parsing_progress' });
    
    const response = await fetch(`${API_BASE_URL}?${queryParams}`);
    if (!response.ok) throw new Error('Failed to fetch parsing progress');
    return response.json();
  }
};