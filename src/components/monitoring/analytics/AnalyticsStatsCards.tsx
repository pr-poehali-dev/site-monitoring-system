import { Card, CardContent } from '@/components/ui/card';
import Icon from '@/components/ui/icon';

interface AnalyticsStatsCardsProps {
  analytics: {
    total_documents: number;
    total_files: number;
    documents_without_files: number;
    documents_with_multiple_files: number;
    total_size_mb: number | string;
    by_section: { section: string; count: number }[];
  };
}

const AnalyticsStatsCards = ({ analytics }: AnalyticsStatsCardsProps) => {
  const formatSize = (mb: number | string) => {
    const mbNum = typeof mb === 'string' ? parseFloat(mb) : mb;
    if (mbNum >= 1024) return `${(mbNum / 1024).toFixed(2)} ГБ`;
    return `${mbNum.toFixed(2)} МБ`;
  };

  return (
    <>
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="text-center">
              <Icon name="FileText" size={24} className="mx-auto text-blue-600 mb-2" />
              <div className="text-3xl font-bold text-gray-900">{analytics.total_documents}</div>
              <div className="text-sm text-gray-500 mt-1">Документов</div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="text-center">
              <Icon name="Files" size={24} className="mx-auto text-green-600 mb-2" />
              <div className="text-3xl font-bold text-gray-900">{analytics.total_files}</div>
              <div className="text-sm text-gray-500 mt-1">Файлов</div>
              {analytics.documents_without_files > 0 && (
                <div className="text-xs text-orange-600 mt-1">
                  {analytics.documents_without_files} док. без файлов
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="text-center">
              <Icon name="HardDrive" size={24} className="mx-auto text-orange-600 mb-2" />
              <div className="text-3xl font-bold text-gray-900">{formatSize(analytics.total_size_mb)}</div>
              <div className="text-sm text-gray-500 mt-1">Общий размер</div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="text-center">
              <Icon name="Layers" size={24} className="mx-auto text-purple-600 mb-2" />
              <div className="text-3xl font-bold text-gray-900">{analytics.by_section.length}</div>
              <div className="text-sm text-gray-500 mt-1">Разделов</div>
              {analytics.documents_with_multiple_files > 0 && (
                <div className="text-xs text-blue-600 mt-1">
                  {analytics.documents_with_multiple_files} док. с приложениями
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {analytics.documents_without_files > 0 && (
        <div className="p-4 border-2 border-orange-200 rounded-lg bg-orange-50">
          <div className="flex items-start gap-3">
            <Icon name="AlertCircle" size={18} className="text-orange-600 mt-0.5" />
            <div className="flex-1">
              <p className="text-sm font-medium text-orange-900">
                Файлов ({analytics.total_files}) меньше, чем документов ({analytics.total_documents})
              </p>
              <p className="text-xs text-orange-700 mt-1">
                <strong>{analytics.documents_without_files} документов</strong> не имеют файлов в базе. 
                Это может быть связано с ошибками загрузки или документы были добавлены до внедрения системы файлов.
              </p>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default AnalyticsStatsCards;
