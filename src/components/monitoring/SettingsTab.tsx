import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import Icon from '@/components/ui/icon';
import ParsingProgress from './ParsingProgress';

interface SettingsTabProps {
  telegramChatId: string;
  setTelegramChatId: (value: string) => void;
  handleSaveSettings: () => void;
  handleRunParser: () => void;
  handleContinueParsing: () => void;
  autoContinue: boolean;
  setAutoContinue: (value: boolean) => void;
  loading: boolean;
}

const SettingsTab = ({
  telegramChatId,
  setTelegramChatId,
  handleSaveSettings,
  handleRunParser,
  handleContinueParsing,
  autoContinue,
  setAutoContinue,
  loading
}: SettingsTabProps) => {
  return (
    <div className="space-y-6">{/* Обёрточный div для нескольких карточек */}
      <ParsingProgress autoRefresh={autoContinue} />
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
          
          <div className="flex items-center justify-between p-4 border rounded-lg">
            <div className="space-y-1">
              <Label htmlFor="auto-continue" className="text-base">Автопродолжение парсинга</Label>
              <p className="text-sm text-gray-500">Автоматически продолжать незавершённые задачи</p>
            </div>
            <div className="flex items-center gap-2">
              {autoContinue && <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse" />}
              <Switch 
                id="auto-continue" 
                checked={autoContinue} 
                onCheckedChange={setAutoContinue}
              />
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
          <Button variant="outline" onClick={handleContinueParsing} disabled={loading}>
            <Icon name="RefreshCw" size={16} className="mr-2" />
            Продолжить
          </Button>
        </div>
      </CardContent>
    </Card>
    </div>{/* Закрывающий div обёртки */}
  );
};

export default SettingsTab;