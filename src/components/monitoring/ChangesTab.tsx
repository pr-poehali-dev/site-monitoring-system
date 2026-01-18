import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import Icon from '@/components/ui/icon';

interface ChangesTabProps {
  changes: any[];
  formatDateTime: (dateStr: string) => string;
  formatFileSize: (bytes: number) => string;
  total: number;
  page: number;
  setPage: (page: number) => void;
  pageSize: number;
  selectedDocumentId?: number | null;
  onClearDocumentFilter: () => void;
}

const ChangesTab = ({ changes, formatDateTime, formatFileSize, total, page, setPage, pageSize, selectedDocumentId, onClearDocumentFilter }: ChangesTabProps) => {
  const totalPages = Math.ceil(total / pageSize);
  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between">
          <div>
            <CardTitle>История изменений</CardTitle>
            <CardDescription>Новые и изменённые документы</CardDescription>
          </div>
          {selectedDocumentId && (
            <Button variant="outline" size="sm" onClick={onClearDocumentFilter}>
              <Icon name="X" size={14} className="mr-1" />
              Показать все
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {selectedDocumentId && (
          <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-lg flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm text-blue-900">
              <Icon name="Filter" size={16} className="text-blue-600" />
              <span>Показаны изменения для документа #{selectedDocumentId}</span>
            </div>
          </div>
        )}
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
                        <div className="mt-3 space-y-2">
                          {change.old_title !== change.new_title && change.old_title && change.new_title && (
                            <div className="text-xs p-2 bg-yellow-50 border border-yellow-200 rounded">
                              <div className="font-medium text-yellow-900 mb-1">📝 Название изменено:</div>
                              <div className="text-yellow-700">
                                <div className="line-through">{change.old_title}</div>
                                <div className="mt-1">→ {change.new_title}</div>
                              </div>
                            </div>
                          )}
                          {change.old_file_size !== change.new_file_size && change.old_file_size && change.new_file_size && (
                            <div className="text-xs p-2 bg-blue-50 border border-blue-200 rounded">
                              <div className="font-medium text-blue-900 mb-1">📦 Размер файла:</div>
                              <div className="text-blue-700">
                                {formatFileSize(change.old_file_size)} → {formatFileSize(change.new_file_size)}
                                {change.new_file_size > change.old_file_size ? ' (увеличился)' : ' (уменьшился)'}
                              </div>
                            </div>
                          )}
                          {change.old_content_hash !== change.new_content_hash && change.old_content_hash && change.new_content_hash && (
                            <div className="text-xs p-2 bg-orange-50 border border-orange-200 rounded">
                              <div className="font-medium text-orange-900 mb-1">📄 Содержимое файла изменено</div>
                              <div className="text-orange-700 flex items-center gap-2">
                                {change.old_file_size === change.new_file_size && (
                                  <span>(размер не изменился, но содержимое обновлено)</span>
                                )}
                              </div>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                    <div className="flex gap-2">
                      <Badge variant={change.change_type === 'new' ? 'default' : 'secondary'}>
                        {change.change_type === 'new' ? 'Новый' : 'Изменён'}
                      </Badge>
                      {change.current_files && change.current_files.length > 0 && (
                        <Button variant="ghost" size="sm" asChild>
                          <a href={change.current_files[0].file_cdn_url || change.current_files[0].file_url} target="_blank" rel="noopener noreferrer" title="Скачать текущую версию">
                            <Icon name="Download" size={14} />
                          </a>
                        </Button>
                      )}
                      {change.url && (
                        <Button variant="ghost" size="sm" asChild>
                          <a href={change.url} target="_blank" rel="noopener noreferrer" title="Открыть на сайте">
                            <Icon name="ExternalLink" size={14} />
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
        {totalPages > 1 && (
          <div className="flex justify-center items-center gap-2 pt-4 border-t">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage(page - 1)}
              disabled={page === 1}
            >
              <Icon name="ChevronLeft" size={16} />
            </Button>
            <div className="text-sm text-gray-600">
              Страница {page} из {totalPages}
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage(page + 1)}
              disabled={page === totalPages}
            >
              <Icon name="ChevronRight" size={16} />
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default ChangesTab;