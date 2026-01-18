import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import Icon from '@/components/ui/icon';

interface MonitoringHeaderProps {
  stats: {
    total_documents: number;
    changes_this_week: number;
    active_sections: number;
  };
}

const MonitoringHeader = ({ stats }: MonitoringHeaderProps) => {
  return (
    <Card className="mb-6">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center">
              <Icon name="FileText" size={24} className="text-blue-600" />
            </div>
            <div>
              <CardTitle className="text-2xl">Мониторинг документов</CardTitle>
              <p className="text-sm text-gray-500 mt-1">
                Система отслеживания нормативных актов
              </p>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <div className="text-center">
              <div className="text-2xl font-bold text-blue-600">{stats.total_documents}</div>
              <div className="text-xs text-gray-500">Документов</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-green-600">{stats.changes_this_week}</div>
              <div className="text-xs text-gray-500">Изменений/неделя</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-orange-600">{stats.active_sections}</div>
              <div className="text-xs text-gray-500">Разделов</div>
            </div>
          </div>
        </div>
      </CardHeader>
    </Card>
  );
};

export default MonitoringHeader;
