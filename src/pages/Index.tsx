import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import Icon from '@/components/ui/icon';
import DocumentsTab from '@/components/monitoring/DocumentsTab';
import ChangesTab from '@/components/monitoring/ChangesTab';
import LogsTab from '@/components/monitoring/LogsTab';
import SettingsTab from '@/components/monitoring/SettingsTab';
import AnalyticsTab from '@/components/monitoring/AnalyticsTab';
import MonitoringHeader from '@/components/monitoring/MonitoringHeader';
import { useMonitoringState } from '@/hooks/useMonitoringState';
import { useMonitoringActions } from '@/hooks/useMonitoringActions';

const Index = () => {
  const state = useMonitoringState();
  
  const actions = useMonitoringActions({
    telegramChatId: state.telegramChatId,
    years: state.years,
    setLoading: state.setLoading,
    setActiveTab: state.setActiveTab,
    setAutoRefreshLogs: state.setAutoRefreshLogs,
    loadAllData: state.loadAllData,
    loadAnalytics: state.loadAnalytics,
    sortBy: state.sortBy,
    sortOrder: state.sortOrder,
    setSortBy: state.setSortBy,
    setSortOrder: state.setSortOrder
  });

  const handleViewDocumentChanges = (documentId: number) => {
    state.setSelectedDocumentId(documentId);
    state.setActiveTab('changes');
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="container mx-auto p-6 max-w-7xl">
        <MonitoringHeader stats={state.stats} />

        <Tabs value={state.activeTab} onValueChange={state.setActiveTab} className="space-y-6">
          <TabsList className="grid w-full grid-cols-5">
            <TabsTrigger value="documents" className="gap-2">
              <Icon name="FileText" size={16} />
              Документы
            </TabsTrigger>
            <TabsTrigger value="changes" className="gap-2">
              <Icon name="GitCommit" size={16} />
              Изменения
            </TabsTrigger>
            <TabsTrigger value="analytics" className="gap-2">
              <Icon name="BarChart3" size={16} />
              Аналитика
            </TabsTrigger>
            <TabsTrigger value="logs" className="gap-2">
              <Icon name="ScrollText" size={16} />
              Логи
            </TabsTrigger>
            <TabsTrigger value="settings" className="gap-2">
              <Icon name="Settings" size={16} />
              Настройки
            </TabsTrigger>
          </TabsList>

          <TabsContent value="documents">
            <DocumentsTab
              documents={state.documents}
              searchQuery={state.searchQuery}
              setSearchQuery={state.setSearchQuery}
              selectedSection={state.selectedSection}
              setSelectedSection={state.setSelectedSection}
              selectedYear={state.selectedYear}
              setSelectedYear={state.setSelectedYear}
              years={state.years}
              sortBy={state.sortBy}
              sortOrder={state.sortOrder}
              handleSort={actions.handleSort}
              getSortIcon={actions.getSortIcon}
              formatDate={actions.formatDate}
              formatDateTime={actions.formatDateTime}
              formatFileSize={actions.formatFileSize}
              total={state.totalDocuments}
              page={state.page}
              setPage={state.setPage}
              pageSize={state.pageSize}
              onViewChanges={handleViewDocumentChanges}
            />
          </TabsContent>

          <TabsContent value="changes">
            <ChangesTab
              changes={state.changes}
              formatDateTime={actions.formatDateTime}
              formatFileSize={actions.formatFileSize}
              total={state.totalChanges}
              page={state.changesPage}
              setPage={state.setChangesPage}
              pageSize={state.changesPageSize}
              selectedDocumentId={state.selectedDocumentId}
              onClearDocumentFilter={() => state.setSelectedDocumentId(null)}
            />
          </TabsContent>

          <TabsContent value="analytics">
            <AnalyticsTab analytics={state.analytics} />
          </TabsContent>

          <TabsContent value="logs">
            <LogsTab
              logs={state.logs}
              autoRefreshLogs={state.autoRefreshLogs}
              setAutoRefreshLogs={state.setAutoRefreshLogs}
              formatDateTime={actions.formatDateTime}
            />
          </TabsContent>

          <TabsContent value="settings">
            <SettingsTab
              telegramChatId={state.telegramChatId}
              setTelegramChatId={state.setTelegramChatId}
              handleSaveSettings={actions.handleSaveSettings}
              handleRunParser={actions.handleRunParser}
              handleContinueParsing={actions.handleContinueParsing}
              handleForceReparse={actions.handleForceReparse}
              handleCleanLogs={actions.handleCleanLogs}
              handleFullReset={actions.handleFullReset}
              handleResetStuck={actions.handleResetStuck}
              loading={state.loading}
            />
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
};

export default Index;