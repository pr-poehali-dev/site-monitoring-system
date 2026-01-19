import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import Icon from '@/components/ui/icon';
import { apiClient } from '@/config/api';

const DocumentVersions = () => {
  const { documentId } = useParams<{ documentId: string }>();
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const loadVersions = async () => {
      if (!documentId) return;
      
      try {
        setLoading(true);
        const result = await apiClient.getDocumentVersions(parseInt(documentId));
        setData(result);
      } catch (err) {
        setError('Не удалось загрузить версии документа');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    loadVersions();
  }, [documentId]);

  const formatDate = (dateStr: string) => {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleDateString('ru-RU', { 
      day: '2-digit', 
      month: '2-digit', 
      year: 'numeric' 
    });
  };

  const formatFileSize = (bytes: number) => {
    if (!bytes) return '-';
    const kb = bytes / 1024;
    if (kb < 1024) return `${kb.toFixed(1)} КБ`;
    return `${(kb / 1024).toFixed(1)} МБ`;
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-gray-600">Загрузка...</div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle className="text-red-600">Ошибка</CardTitle>
            <CardDescription>{error || 'Документ не найден'}</CardDescription>
          </CardHeader>
          <CardContent>
            <Link to="/">
              <Button variant="outline" className="w-full">
                <Icon name="ArrowLeft" size={16} className="mr-2" />
                Вернуться к документам
              </Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    );
  }

  const { latest, versions, total_versions } = data;

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="container mx-auto p-6 max-w-7xl">
        <div className="mb-6">
          <Link to="/">
            <Button variant="outline" size="sm">
              <Icon name="ArrowLeft" size={16} className="mr-2" />
              Назад к документам
            </Button>
          </Link>
        </div>

        <Card className="mb-6">
          <CardHeader>
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <CardTitle className="text-xl mb-2">Версии документа</CardTitle>
                <CardDescription>
                  Актуальная версия и история изменений
                </CardDescription>
              </div>
              <Badge variant="secondary" className="text-sm">
                {total_versions} {total_versions === 1 ? 'версия' : total_versions < 5 ? 'версии' : 'версий'}
              </Badge>
            </div>
          </CardHeader>
          <CardContent>
            <div className="p-4 bg-green-50 border border-green-200 rounded-lg">
              <div className="flex items-start gap-3">
                <Icon name="CheckCircle2" size={20} className="text-green-600 mt-0.5" />
                <div className="flex-1">
                  <div className="font-semibold text-green-900 mb-1">
                    Актуальная версия <Badge variant="default" className="ml-2 text-xs bg-green-600">Действует</Badge>
                  </div>
                  <div className="text-sm text-green-800 mb-2">{latest.title}</div>
                  <div className="flex gap-4 text-xs text-green-700">
                    <div>
                      <span className="font-medium">Номер:</span> {latest.document_number || '-'}
                    </div>
                    <div>
                      <span className="font-medium">Дата:</span> {formatDate(latest.document_date)}
                    </div>
                    <div>
                      <span className="font-medium">Раздел:</span> {latest.section}
                    </div>
                  </div>
                  {latest.files && latest.files.length > 0 && (
                    <div className="mt-3 flex gap-2">
                      {latest.files.map((file: any, idx: number) => (
                        <Button 
                          key={idx} 
                          variant={file.file_type === 'main' ? 'default' : 'outline'} 
                          size="sm" 
                          asChild
                        >
                          <a 
                            href={file.file_cdn_url || file.file_url} 
                            target="_blank" 
                            rel="noopener noreferrer"
                          >
                            <Icon name="Download" size={14} className="mr-1" />
                            {file.file_type === 'main' ? 'Основной файл' : 'Приложение'}
                          </a>
                        </Button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {versions.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>Предыдущие версии</CardTitle>
              <CardDescription>
                История изменений документа (от новых к старым)
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="border rounded-lg overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Название</TableHead>
                      <TableHead>Номер</TableHead>
                      <TableHead>Дата документа</TableHead>
                      <TableHead>Дата публикации</TableHead>
                      <TableHead>Раздел</TableHead>
                      <TableHead className="text-right">Файлы</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {versions.map((version: any) => (
                      <TableRow key={version.id}>
                        <TableCell>
                          <div className="max-w-md">
                            <div className="font-medium text-gray-900 text-sm">
                              {version.title}
                            </div>
                          </div>
                        </TableCell>
                        <TableCell className="text-gray-600 text-sm">
                          {version.document_number || '-'}
                        </TableCell>
                        <TableCell className="text-gray-600 text-sm">
                          {formatDate(version.document_date)}
                        </TableCell>
                        <TableCell className="text-gray-600 text-sm">
                          {formatDate(version.published_date)}
                        </TableCell>
                        <TableCell>
                          <Badge variant="secondary" className="text-xs">
                            {version.section}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-right">
                          {version.files && version.files.length > 0 ? (
                            <div className="flex flex-col gap-1 items-end">
                              {version.files.map((file: any, idx: number) => (
                                <Button 
                                  key={idx} 
                                  variant={file.file_type === 'main' ? 'default' : 'outline'} 
                                  size="sm" 
                                  asChild
                                >
                                  <a 
                                    href={file.file_cdn_url || file.file_url} 
                                    target="_blank" 
                                    rel="noopener noreferrer"
                                  >
                                    <Icon name="Download" size={14} className="mr-1" />
                                    {formatFileSize(file.file_size)}
                                  </a>
                                </Button>
                              ))}
                            </div>
                          ) : (
                            <span className="text-gray-400 text-xs">Нет файлов</span>
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        )}

        {versions.length === 0 && (
          <Card>
            <CardContent className="py-12">
              <div className="text-center text-gray-500">
                <Icon name="FileQuestion" size={48} className="mx-auto mb-4 text-gray-400" />
                <p className="text-lg font-medium mb-1">Нет версий</p>
                <p className="text-sm">У этого документа пока нет изменений</p>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
};

export default DocumentVersions;