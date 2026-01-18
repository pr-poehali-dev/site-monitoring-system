import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import Icon from '@/components/ui/icon';
import { apiClient } from '@/config/api';
import { useToast } from '@/hooks/use-toast';

const Index = () => {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedSection, setSelectedSection] = useState('all');
  const [selectedYear, setSelectedYear] = useState('all');
  const [sortBy, setSortBy] = useState('created_at');
  const [sortOrder, setSortOrder] = useState('DESC');
  const [documents, setDocuments] = useState<any[]>([]);
  const [changes, setChanges] = useState<any[]>([]);
  const [logs, setLogs] = useState<any[]>([]);
  const [stats, setStats] = useState({ total_documents: 0, changes_this_week: 0, active_sections: 0 });
  const [settings, setSettings] = useState<any>({});
  const [loading, setLoading] = useState(false);
  const [telegramChatId, setTelegramChatId] = useState('');
  const [activeTab, setActiveTab] = useState('documents');
  const [autoRefreshLogs, setAutoRefreshLogs] = useState(false);
  const { toast } = useToast();

  const currentYear = new Date().getFullYear();
  const years = Array.from({ length: currentYear - 2008 }, (_, i) => (2009 + i).toString());

  useEffect(() => {
    loadAllData();
  }, []);

  useEffect(() => {
    loadDocuments();
  }, [searchQuery, selectedSection, selectedYear, sortBy, sortOrder]);

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

  const loadAllData = async () => {
    try {
      const [statsData, docsData, changesData, logsData, settingsData] = await Promise.all([
        apiClient.getStats(),
        apiClient.getDocuments({ limit: 100 }),
        apiClient.getChanges(50),
        apiClient.getLogs(50),
        apiClient.getSettings()
      ]);
      
      setStats(statsData);
      setDocuments(docsData.documents || []);
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
      const params: any = { limit: 100 };
      if (searchQuery) params.search = searchQuery;
      if (selectedSection !== 'all') params.section = selectedSection;
      if (selectedYear !== 'all') params.year = selectedYear;
      params.sort_by = sortBy;
      params.sort_order = sortOrder;

      const docsData = await apiClient.getDocuments(params);
      setDocuments(docsData.documents || []);
    } catch (error) {
      console.error('Failed to load documents:', error);
    }
  };

  const handleSaveSettings = async () => {
    try {
      await apiClient.updateSettings({ telegram_chat_id: telegramChatId });
      toast({
        title: 'Настройки сохранены',
        description: `Telegram Chat ID: ${telegramChatId}`
      });
      await loadAllData();
    } catch (error) {
      toast({
        title: 'Ошибка',
        description: 'Не удалось сохранить настройки',
        variant: 'destructive'
      });
    }
  };

  const handleRunParser = async () => {
    setLoading(true);
    setActiveTab('logs');
    setAutoRefreshLogs(true);
    
    try {
      apiClient.runParser(['postanovleniya', 'rasporyazheniya', 'programmy'], years.map(y => parseInt(y)));
      
      toast({
        title: 'Парсинг запущен в фоне',
        description: `Система начала сканирование документов за ${years.length} лет (2009-${currentYear}). Логи обновляются автоматически.`
      });
    } catch (error) {
      toast({
        title: 'Ошибка',
        description: 'Не удалось запустить парсинг',
        variant: 'destructive'
      });
      setAutoRefreshLogs(false);
    } finally {
      setLoading(false);
    }
  };

  const formatFileSize = (bytes: number) => {
    if (!bytes) return '-';
    const kb = bytes / 1024;
    if (kb < 1024) return `${kb.toFixed(1)} КБ`;
    return `${(kb / 1024).toFixed(1)} МБ`;
  };

  const formatDate = (dateStr: string) => {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleDateString('ru-RU', { 
      day: '2-digit', 
      month: '2-digit', 
      year: 'numeric' 
    });
  };

  const formatDateTime = (dateStr: string) => {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const handleSort = (field: string) => {
    if (sortBy === field) {
      setSortOrder(sortOrder === 'DESC' ? 'ASC' : 'DESC');
    } else {
      setSortBy(field);
      setSortOrder('DESC');
    }
  };

  const getSortIcon = (field: string) => {
    if (sortBy !== field) return null;
    return sortOrder === 'DESC' ? '↓' : '↑';
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Icon name="FileSearch" size={24} className="text-primary" />
            <h1 className="text-xl font-semibold text-gray-900">Мониторинг документов</h1>
          </div>
          <Badge variant="outline" className="gap-2">
            <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
            Активен
          </Badge>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium text-gray-600">Всего документов</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-end justify-between">
                <div className="text-3xl font-bold text-gray-900">{stats.total_documents.toLocaleString()}</div>
                <Icon name="FileText" size={20} className="text-gray-400" />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium text-gray-600">Изменений за неделю</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-end justify-between">
                <div className="text-3xl font-bold text-gray-900">{stats.changes_this_week}</div>
                <Icon name="TrendingUp" size={20} className="text-green-500" />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium text-gray-600">Активных разделов</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-end justify-between">
                <div className="text-3xl font-bold text-gray-900">{stats.active_sections}</div>
                <Icon name="Folders" size={20} className="text-gray-400" />
              </div>
            </CardContent>
          </Card>
        </div>

        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
          <TabsList>
            <TabsTrigger value="documents" className="gap-2">
              <Icon name="FileText" size={16} />
              Документы
            </TabsTrigger>
            <TabsTrigger value="changes" className="gap-2">
              <Icon name="Bell" size={16} />
              Изменения
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
            <Card>
              <CardHeader>
                <CardTitle>База документов</CardTitle>
                <CardDescription>Все отслеживаемые документы с метаданными</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex gap-4 flex-wrap">
                  <div className="flex-1 min-w-[200px]">
                    <Input
                      placeholder="Поиск по названию..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="w-full"
                    />
                  </div>
                  <Select value={selectedSection} onValueChange={setSelectedSection}>
                    <SelectTrigger className="w-[200px]">
                      <SelectValue placeholder="Все разделы" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">Все разделы</SelectItem>
                      <SelectItem value="Постановления">Постановления</SelectItem>
                      <SelectItem value="Распоряжения">Распоряжения</SelectItem>
                      <SelectItem value="Муниципальные программы">Программы</SelectItem>
                    </SelectContent>
                  </Select>
                  <Select value={selectedYear} onValueChange={setSelectedYear}>
                    <SelectTrigger className="w-[150px]">
                      <SelectValue placeholder="Все годы" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">Все годы</SelectItem>
                      {years.reverse().map(year => (
                        <SelectItem key={year} value={year}>{year}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="border rounded-lg overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead 
                          className="cursor-pointer hover:bg-gray-50"
                          onClick={() => handleSort('title')}
                        >
                          Название {getSortIcon('title')}
                        </TableHead>
                        <TableHead>Раздел</TableHead>
                        <TableHead 
                          className="cursor-pointer hover:bg-gray-50"
                          onClick={() => handleSort('document_date')}
                        >
                          Дата документа {getSortIcon('document_date')}
                        </TableHead>
                        <TableHead 
                          className="cursor-pointer hover:bg-gray-50"
                          onClick={() => handleSort('created_at')}
                        >
                          Загружено {getSortIcon('created_at')}
                        </TableHead>
                        <TableHead 
                          className="cursor-pointer hover:bg-gray-50"
                          onClick={() => handleSort('file_size')}
                        >
                          Размер {getSortIcon('file_size')}
                        </TableHead>
                        <TableHead 
                          className="cursor-pointer hover:bg-gray-50 text-center"
                          onClick={() => handleSort('changes_count')}
                        >
                          Изменений {getSortIcon('changes_count')}
                        </TableHead>
                        <TableHead className="text-right">Файл</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {documents.map((doc) => (
                        <TableRow key={doc.id}>
                          <TableCell>
                            <div className="space-y-1 max-w-md">
                              <div className="font-medium text-gray-900 text-sm">{doc.title}</div>
                              {doc.document_number && (
                                <div className="text-xs text-gray-500">№ {doc.document_number}</div>
                              )}
                            </div>
                          </TableCell>
                          <TableCell>
                            <Badge variant="secondary" className="text-xs">{doc.section}</Badge>
                          </TableCell>
                          <TableCell className="text-gray-600 text-sm">
                            {formatDate(doc.document_date)}
                          </TableCell>
                          <TableCell className="text-gray-600 text-sm">
                            {formatDateTime(doc.created_at)}
                          </TableCell>
                          <TableCell className="text-gray-600 text-sm">
                            {formatFileSize(doc.file_size)}
                          </TableCell>
                          <TableCell className="text-center">
                            {doc.changes_count > 0 ? (
                              <Badge variant="outline" className="text-xs">
                                {doc.changes_count}
                              </Badge>
                            ) : (
                              <span className="text-gray-400 text-xs">0</span>
                            )}
                          </TableCell>
                          <TableCell className="text-right">
                            <Button variant="ghost" size="sm" asChild>
                              <a 
                                href={doc.file_cdn_url || doc.url} 
                                target="_blank" 
                                rel="noopener noreferrer"
                              >
                                <Icon name="Download" size={16} />
                              </a>
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>

                <div className="flex justify-between items-center text-sm text-gray-600">
                  <div>Показано документов: {documents.length}</div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="changes">
            <Card>
              <CardHeader>
                <CardTitle>История изменений</CardTitle>
                <CardDescription>Новые и изменённые документы</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {changes.length === 0 ? (
                    <div className="text-center py-8 text-gray-500">
                      Нет обнаруженных изменений
                    </div>
                  ) : (
                    changes.map((change) => (
                      <div key={change.id} className="flex gap-4 p-4 border rounded-lg hover:bg-gray-50 transition-colors">
                        <div className="flex-shrink-0 mt-1">
                          {change.change_type === 'new' ? (
                            <div className="w-10 h-10 rounded-full bg-green-100 flex items-center justify-center">
                              <Icon name="Plus" size={20} className="text-green-600" />
                            </div>
                          ) : (
                            <div className="w-10 h-10 rounded-full bg-orange-100 flex items-center justify-center">
                              <Icon name="Pencil" size={20} className="text-orange-600" />
                            </div>
                          )}
                        </div>
                        <div className="flex-1 space-y-2">
                          <div className="flex items-start justify-between">
                            <div>
                              <div className="font-medium text-gray-900">
                                {change.change_type === 'new' ? change.new_title : change.title}
                              </div>
                              <div className="text-sm text-gray-600 mt-1">
                                <Badge variant="secondary" className="mr-2">{change.section}</Badge>
                                <span className="text-xs text-gray-500">
                                  {formatDateTime(change.detected_at)}
                                </span>
                              </div>
                              {change.change_type === 'modified' && (
                                <div className="text-xs text-gray-500 mt-2">
                                  {change.old_file_size && change.new_file_size && (
                                    <div>Размер: {formatFileSize(change.old_file_size)} → {formatFileSize(change.new_file_size)}</div>
                                  )}
                                </div>
                              )}
                            </div>
                            <div className="flex gap-2">
                              <Badge variant={change.change_type === 'new' ? 'default' : 'secondary'}>
                                {change.change_type === 'new' ? 'Новый' : 'Изменён'}
                              </Badge>
                              {change.file_cdn_url && (
                                <Button variant="ghost" size="sm" asChild>
                                  <a href={change.file_cdn_url} target="_blank" rel="noopener noreferrer">
                                    <Icon name="Download" size={14} />
                                  </a>
                                </Button>
                              )}
                            </div>
                          </div>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="logs">
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle>Логи парсинга</CardTitle>
                    <CardDescription>Подробная информация о работе системы</CardDescription>
                  </div>
                  <div className="flex items-center gap-3">
                    <Label htmlFor="auto-refresh" className="text-sm cursor-pointer">
                      <div className="flex items-center gap-2">
                        {autoRefreshLogs && <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />}
                        Автообновление
                      </div>
                    </Label>
                    <Switch 
                      id="auto-refresh" 
                      checked={autoRefreshLogs} 
                      onCheckedChange={setAutoRefreshLogs}
                    />
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {logs.length === 0 ? (
                    <div className="text-center py-8 text-gray-500">
                      Нет записей в логах
                    </div>
                  ) : (
                    logs.map((log) => (
                      <div key={log.id} className="flex gap-3 p-3 border rounded-lg font-mono text-sm">
                        <div className="flex-shrink-0">
                          {log.status === 'success' && (
                            <Icon name="CheckCircle2" size={18} className="text-green-600" />
                          )}
                          {log.status === 'info' && (
                            <Icon name="Info" size={18} className="text-blue-600" />
                          )}
                          {log.status === 'error' && (
                            <Icon name="XCircle" size={18} className="text-red-600" />
                          )}
                          {log.status === 'warning' && (
                            <Icon name="AlertTriangle" size={18} className="text-orange-600" />
                          )}
                        </div>
                        <div className="flex-1 space-y-1">
                          <div className="flex items-center gap-3 text-gray-500 text-xs">
                            <span>{formatDateTime(log.started_at)}</span>
                            <span>•</span>
                            <span>{log.duration_ms ? `${log.duration_ms}ms` : '-'}</span>
                          </div>
                          <div className="text-gray-900 whitespace-pre-wrap">{log.message}</div>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="settings">
            <Card>
              <CardHeader>
                <CardTitle>Настройки мониторинга</CardTitle>
                <CardDescription>Управление параметрами системы</CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="space-y-4">
                  <h3 className="font-semibold text-gray-900">Уведомления</h3>
                  
                  <div className="space-y-3">
                    <div className="flex items-center justify-between p-4 border rounded-lg">
                      <div className="space-y-1">
                        <Label htmlFor="notify-telegram" className="text-base">Telegram уведомления</Label>
                        <p className="text-sm text-gray-500">Отправлять сообщения о новых документах</p>
                      </div>
                      <Switch id="notify-telegram" defaultChecked />
                    </div>

                    <div className="p-4 border rounded-lg space-y-3">
                      <Label htmlFor="telegram-chat">Telegram Chat ID</Label>
                      <Input 
                        id="telegram-chat" 
                        placeholder="3642302397" 
                        className="font-mono"
                        value={telegramChatId}
                        onChange={(e) => setTelegramChatId(e.target.value)}
                      />
                      <p className="text-xs text-gray-500">Chat ID: {telegramChatId || 'не указан'}</p>
                    </div>
                  </div>
                </div>

                <div className="flex gap-3 pt-4 border-t">
                  <Button className="flex-1" onClick={handleSaveSettings}>
                    <Icon name="Save" size={16} className="mr-2" />
                    Сохранить настройки
                  </Button>
                  <Button variant="outline" onClick={handleRunParser} disabled={loading}>
                    <Icon name="Play" size={16} className="mr-2" />
                    {loading ? 'Запуск...' : 'Запустить парсинг'}
                  </Button>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </main>
    </div>
  );
};

export default Index;
