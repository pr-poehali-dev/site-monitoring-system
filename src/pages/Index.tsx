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
  const [documents, setDocuments] = useState<any[]>([]);
  const [changes, setChanges] = useState<any[]>([]);
  const [logs, setLogs] = useState<any[]>([]);
  const [stats, setStats] = useState({ total_documents: 0, changes_this_week: 0, active_sections: 0 });
  const [settings, setSettings] = useState<any>({});
  const [loading, setLoading] = useState(false);
  const { toast } = useToast();

  useEffect(() => {
    loadAllData();
  }, []);

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
    } catch (error) {
      console.error('Failed to load data:', error);
    }
  };

  const handleRunParser = async () => {
    setLoading(true);
    try {
      await apiClient.runParser(['postanovleniya', 'rasporyazheniya', 'programmy'], [2024, 2025]);
      toast({
        title: 'Парсинг запущен',
        description: 'Система начала сканирование документов'
      });
      setTimeout(() => loadAllData(), 5000);
    } catch (error) {
      toast({
        title: 'Ошибка',
        description: 'Не удалось запустить парсинг',
        variant: 'destructive'
      });
    } finally {
      setLoading(false);
    }
  };

  const filteredDocuments = documents.filter(doc => {
    const matchesSearch = doc.title.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesSection = selectedSection === 'all' || doc.section === selectedSection;
    return matchesSearch && matchesSection;
  });

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

        <Tabs defaultValue="documents" className="space-y-6">
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
                <div className="flex gap-4">
                  <div className="flex-1">
                    <Input
                      placeholder="Поиск по названию документа..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="w-full"
                    />
                  </div>
                  <Select value={selectedSection} onValueChange={setSelectedSection}>
                    <SelectTrigger className="w-[240px]">
                      <SelectValue placeholder="Все разделы" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">Все разделы</SelectItem>
                      <SelectItem value="Постановления">Постановления</SelectItem>
                      <SelectItem value="Распоряжения">Распоряжения</SelectItem>
                      <SelectItem value="Муниципальные программы">Муниципальные программы</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="border rounded-lg">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Название</TableHead>
                        <TableHead>Раздел</TableHead>
                        <TableHead>Дата публикации</TableHead>
                        <TableHead className="text-right">Действия</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {filteredDocuments.map((doc) => (
                        <TableRow key={doc.id}>
                          <TableCell>
                            <div className="space-y-1">
                              <div className="font-medium text-gray-900">{doc.title}</div>
                              <div className="text-xs font-mono text-gray-500">{doc.url}</div>
                            </div>
                          </TableCell>
                          <TableCell>
                            <Badge variant="secondary">{doc.section}</Badge>
                          </TableCell>
                          <TableCell className="text-gray-600">
                            {doc.published_date ? new Date(doc.published_date).toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric' }) : '-'}
                          </TableCell>
                          <TableCell className="text-right">
                            <Button variant="ghost" size="sm" asChild>
                              <a href={doc.url} target="_blank" rel="noopener noreferrer">
                                <Icon name="ExternalLink" size={16} />
                              </a>
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>

                <div className="flex justify-between items-center text-sm text-gray-600">
                  <div>Показано {filteredDocuments.length} из {documents.length}</div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="changes">
            <Card>
              <CardHeader>
                <CardTitle>История изменений</CardTitle>
                <CardDescription>Новые и изменённые документы, обнаруженные системой</CardDescription>
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
                              <div className="font-medium text-gray-900">{change.title}</div>
                              <div className="text-sm text-gray-600 mt-1">
                                <Badge variant="secondary" className="mr-2">{change.section}</Badge>
                                <span className="text-xs text-gray-500">
                                  {new Date(change.detected_at).toLocaleString('ru-RU')}
                                </span>
                              </div>
                            </div>
                            <Badge variant={change.change_type === 'new' ? 'default' : 'secondary'}>
                              {change.change_type === 'new' ? 'Новый' : 'Изменён'}
                            </Badge>
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
                <CardTitle>Логи парсинга</CardTitle>
                <CardDescription>Подробная информация о работе системы мониторинга</CardDescription>
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
                        </div>
                        <div className="flex-1 space-y-1">
                          <div className="flex items-center gap-3 text-gray-500 text-xs">
                            <span>{new Date(log.started_at).toLocaleString('ru-RU')}</span>
                            <span>•</span>
                            <span>{log.duration_ms ? `${log.duration_ms}ms` : '-'}</span>
                          </div>
                          <div className="text-gray-900">{log.message}</div>
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
                  <h3 className="font-semibold text-gray-900">Отслеживаемые разделы</h3>
                  
                  <div className="space-y-3">
                    <div className="flex items-center justify-between p-4 border rounded-lg">
                      <div className="space-y-1">
                        <Label htmlFor="section-postanovleniya" className="text-base">Постановления</Label>
                        <p className="text-sm text-gray-500">/docs/smolensk/postanovleniya/</p>
                      </div>
                      <Switch id="section-postanovleniya" defaultChecked />
                    </div>

                    <div className="flex items-center justify-between p-4 border rounded-lg">
                      <div className="space-y-1">
                        <Label htmlFor="section-rasporyazheniya" className="text-base">Распоряжения</Label>
                        <p className="text-sm text-gray-500">/docs/smolensk/rasporyazheniya/</p>
                      </div>
                      <Switch id="section-rasporyazheniya" defaultChecked />
                    </div>

                    <div className="flex items-center justify-between p-4 border rounded-lg">
                      <div className="space-y-1">
                        <Label htmlFor="section-programmy" className="text-base">Муниципальные программы</Label>
                        <p className="text-sm text-gray-500">/docs/municipalnye-programmy/</p>
                      </div>
                      <Switch id="section-programmy" defaultChecked />
                    </div>
                  </div>
                </div>

                <div className="space-y-4 pt-6 border-t">
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
                        placeholder="-1001234567890" 
                        className="font-mono"
                      />
                    </div>
                  </div>
                </div>

                <div className="space-y-4 pt-6 border-t">
                  <h3 className="font-semibold text-gray-900">Расписание проверки</h3>
                  
                  <div className="p-4 border rounded-lg space-y-3">
                    <Label>Частота мониторинга</Label>
                    <Select defaultValue="daily">
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="hourly">Каждый час</SelectItem>
                        <SelectItem value="daily">Ежедневно (14:30)</SelectItem>
                        <SelectItem value="weekly">Еженедельно</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                <div className="flex gap-3 pt-4">
                  <Button className="flex-1">
                    <Icon name="Save" size={16} className="mr-2" />
                    Сохранить настройки
                  </Button>
                  <Button variant="outline" onClick={handleRunParser} disabled={loading}>
                    <Icon name="Play" size={16} className="mr-2" />
                    {loading ? 'Запуск...' : 'Запустить проверку'}
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