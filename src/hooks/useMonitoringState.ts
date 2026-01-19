import { useState, useEffect } from 'react';
import { apiClient } from '@/config/api';

export const useMonitoringState = () => {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedSection, setSelectedSection] = useState('all');
  const [selectedYear, setSelectedYear] = useState('all');
  const [onlyActual, setOnlyActual] = useState(false);
  const [onlyReal, setOnlyReal] = useState(false);
  const [sortBy, setSortBy] = useState('document_date');
  const [sortOrder, setSortOrder] = useState('DESC');
  const [documents, setDocuments] = useState<any[]>([]);
  const [totalDocuments, setTotalDocuments] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [changes, setChanges] = useState<any[]>([]);
  const [totalChanges, setTotalChanges] = useState(0);
  const [changesPage, setChangesPage] = useState(1);
  const [changesPageSize] = useState(20);
  const [logs, setLogs] = useState<any[]>([]);
  const [stats, setStats] = useState({ total_documents: 0, changes_this_week: 0, active_sections: 0 });
  const [settings, setSettings] = useState<any>({});
  const [loading, setLoading] = useState(false);
  const [telegramChatId, setTelegramChatId] = useState('');
  const [activeTab, setActiveTab] = useState('documents');
  const [autoRefreshLogs, setAutoRefreshLogs] = useState(false);
  const [selectedDocumentId, setSelectedDocumentId] = useState<number | null>(null);
  const [analytics, setAnalytics] = useState<any>(null);

  const currentYear = new Date().getFullYear();
  const years = Array.from({ length: currentYear - 2008 }, (_, i) => (2009 + i).toString());

  const loadAllData = async () => {
    try {
      const [statsData, docsData, changesData, logsData, settingsData] = await Promise.all([
        apiClient.getStats(),
        apiClient.getDocuments({ limit: 100, sort_by: 'document_date', sort_order: 'DESC' }),
        apiClient.getChanges(50),
        apiClient.getLogs(50),
        apiClient.getSettings()
      ]);
      
      setStats(statsData);
      setDocuments(docsData.documents || []);
      setTotalDocuments(docsData.total || 0);
      setChanges(changesData.changes || []);
      setLogs(logsData.logs || []);
      setSettings(settingsData.settings || {});
      setTelegramChatId(settingsData.settings?.telegram_chat_id || '');
    } catch (error) {
      console.error('Failed to load data:', error);
    }
  };

  const loadDocuments = async () => {
    try {
      const params: any = { 
        limit: pageSize,
        offset: (page - 1) * pageSize
      };
      if (searchQuery) params.search = searchQuery;
      if (selectedSection !== 'all') params.section = selectedSection;
      if (selectedYear !== 'all') params.year = selectedYear;
      if (onlyActual) params.only_actual = 'true';
      if (onlyReal) params.only_real = 'true';
      params.sort_by = sortBy;
      params.sort_order = sortOrder;

      const docsData = await apiClient.getDocuments(params);
      setDocuments(docsData.documents || []);
      setTotalDocuments(docsData.total || 0);
    } catch (error) {
      console.error('Failed to load documents:', error);
    }
  };

  const loadChanges = async () => {
    try {
      const params: any = { limit: changesPageSize };
      if (selectedDocumentId) {
        params.document_id = selectedDocumentId;
      }
      const changesData = await apiClient.getChanges(params.limit, params.document_id);
      setChanges(changesData.changes || []);
      setTotalChanges(changesData.changes?.length || 0);
    } catch (error) {
      console.error('Failed to load changes:', error);
    }
  };

  const loadAnalytics = async () => {
    try {
      const analyticsData = await apiClient.getAnalytics();
      setAnalytics(analyticsData);
    } catch (error) {
      console.error('Failed to load analytics:', error);
    }
  };

  useEffect(() => {
    loadAllData();
    loadAnalytics();
  }, []);

  useEffect(() => {
    setPage(1);
  }, [searchQuery, selectedSection, selectedYear, onlyActual, onlyReal]);

  useEffect(() => {
    loadDocuments();
  }, [searchQuery, selectedSection, selectedYear, onlyActual, onlyReal, sortBy, sortOrder, page]);

  useEffect(() => {
    loadChanges();
  }, [selectedDocumentId, changesPage]);

  useEffect(() => {
    if (autoRefreshLogs) {
      const interval = setInterval(async () => {
        try {
          const [logsData, statsData] = await Promise.all([
            apiClient.getLogs(50),
            apiClient.getStats()
          ]);
          setLogs(logsData.logs || []);
          setStats(statsData);
        } catch (error) {
          console.error('Failed to refresh logs:', error);
        }
      }, 3000);

      return () => clearInterval(interval);
    }
  }, [autoRefreshLogs]);

  return {
    searchQuery,
    setSearchQuery,
    selectedSection,
    setSelectedSection,
    selectedYear,
    setSelectedYear,
    onlyActual,
    setOnlyActual,
    onlyReal,
    setOnlyReal,
    sortBy,
    setSortBy,
    sortOrder,
    setSortOrder,
    documents,
    totalDocuments,
    page,
    setPage,
    pageSize,
    changes,
    totalChanges,
    changesPage,
    setChangesPage,
    changesPageSize,
    logs,
    stats,
    settings,
    loading,
    setLoading,
    telegramChatId,
    setTelegramChatId,
    activeTab,
    setActiveTab,
    autoRefreshLogs,
    setAutoRefreshLogs,
    selectedDocumentId,
    setSelectedDocumentId,
    analytics,
    years,
    loadAllData,
    loadAnalytics
  };
};