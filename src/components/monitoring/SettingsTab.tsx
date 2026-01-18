import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import Icon from '@/components/ui/icon';
import ParsingProgress from './ParsingProgress';
import FileDownloadPanel from './FileDownloadPanel';
import MissingFilesPanel from './MissingFilesPanel';

interface SettingsTabProps {
  telegramChatId: string;
  setTelegramChatId: (value: string) => void;
  handleSaveSettings: () => void;
  handleRunParser: () => void;
  handleContinueParsing: () => void;
  handleForceReparse: () => void;
  handleCleanLogs: () => void;
  handleFullReset: () => void;
  loading: boolean;
}

const SettingsTab = ({
  telegramChatId,
  setTelegramChatId,
  handleSaveSettings,
  handleRunParser,
  handleContinueParsing,
  handleForceReparse,
  handleCleanLogs,
  handleFullReset,
  loading
}: SettingsTabProps) => {
  return (
    <div className="space-y-6">
      <ParsingProgress autoRefresh={true} />
      <MissingFilesPanel />
      <FileDownloadPanel />
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

        <div className="space-y-4">
          <h3 className="font-semibold text-gray-900 pt-4 border-t">Парсинг</h3>
          
          <div className="p-4 border rounded-lg bg-blue-50 border-blue-200">
            <div className="flex items-start gap-3">
              <Icon name="Info" size={18} className="text-blue-600 mt-0.5" />
              <div className="space-y-1">
                <p className="text-sm font-medium text-blue-900">Автономный режим</p>
                <p className="text-xs text-blue-700">Парсинг работает в фоне на сервере. Можно закрыть страницу — процесс продолжится автоматически до завершения.</p>
              </div>
            </div>
          </div>
        </div>

        <div className="space-y-3 pt-4 border-t">
          <Button className="w-full" onClick={handleSaveSettings}>
            <Icon name="Save" size={16} className="mr-2" />
            Сохранить настройки
          </Button>
          
          <div className="grid grid-cols-2 gap-3">
            <Button variant="outline" onClick={handleRunParser} disabled={loading}>
              <Icon name="Play" size={16} className="mr-2" />
              {loading ? 'Запуск...' : 'Запустить парсинг'}
            </Button>
            <Button variant="outline" onClick={handleContinueParsing} disabled={loading}>
              <Icon name="RefreshCw" size={16} className="mr-2" />
              Продолжить
            </Button>
          </div>

          <Button 
            variant="destructive" 
            className="w-full"
            onClick={handleForceReparse} 
            disabled={loading}
          >
            <Icon name="RotateCcw" size={16} className="mr-2" />
            Перезапустить всё с нуля
          </Button>
          <p className="text-xs text-gray-500 text-center">
            ⚠️ Все документы будут спарсены заново (может занять ~1 час)
          </p>

          <div className="pt-4 border-t space-y-4">
            <div>
              <Button 
                variant="outline" 
                className="w-full"
                onClick={handleCleanLogs}
              >
                <Icon name="Trash2" size={16} className="mr-2" />
                Очистить старые логи
              </Button>
              <p className="text-xs text-gray-500 text-center mt-2">
                Удалить логи парсинга старше 7 дней
              </p>
            </div>

            <div>
              <Button 
                variant="destructive" 
                className="w-full"
                onClick={handleFullReset}
                disabled={loading}
              >
                <Icon name="AlertTriangle" size={16} className="mr-2" />
                🚨 ПОЛНЫЙ СБРОС БАЗЫ ДАННЫХ
              </Button>
              <p className="text-xs text-red-600 text-center mt-2 font-medium">
                ⚠️ Удалит ВСЕ документы, файлы, изменения и логи!
              </p>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
    </div>
  );
};

export default SettingsTab;