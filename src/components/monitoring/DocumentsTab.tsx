import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import Icon from '@/components/ui/icon';

interface DocumentsTabProps {
  documents: any[];
  searchQuery: string;
  setSearchQuery: (value: string) => void;
  selectedSection: string;
  setSelectedSection: (value: string) => void;
  selectedYear: string;
  setSelectedYear: (value: string) => void;
  onlyActual: boolean;
  setOnlyActual: (value: boolean) => void;
  onlyReal: boolean;
  setOnlyReal: (value: boolean) => void;
  years: string[];
  sortBy: string;
  sortOrder: string;
  handleSort: (field: string) => void;
  getSortIcon: (field: string) => string | null;
  formatDate: (dateStr: string) => string;
  formatDateTime: (dateStr: string) => string;
  formatFileSize: (bytes: number) => string;
  total: number;
  page: number;
  setPage: (page: number) => void;
  pageSize: number;
  onViewChanges: (documentId: number) => void;
}

const DocumentsTab = ({
  documents,
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
  years,
  sortBy,
  sortOrder,
  handleSort,
  getSortIcon,
  formatDate,
  formatDateTime,
  formatFileSize,
  total,
  page,
  setPage,
  pageSize,
  onViewChanges
}: DocumentsTabProps) => {
  const totalPages = Math.ceil(total / pageSize);
  return (
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
          <div className="flex items-center space-x-2">
            <Checkbox 
              id="only-actual" 
              checked={onlyActual}
              onCheckedChange={setOnlyActual}
            />
            <Label htmlFor="only-actual" className="text-sm font-normal cursor-pointer">
              Только актуальные
            </Label>
          </div>
          <div className="flex items-center space-x-2">
            <Checkbox 
              id="only-real" 
              checked={onlyReal}
              onCheckedChange={setOnlyReal}
            />
            <Label htmlFor="only-real" className="text-sm font-normal cursor-pointer">
              Только реальные документы
            </Label>
          </div>
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
                  onClick={() => handleSort('published_date')}
                >
                  Дата публикации {getSortIcon('published_date')}
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
                <TableHead 
                  className="cursor-pointer hover:bg-gray-50 text-center"
                  onClick={() => handleSort('related_count')}
                >
                  Версии {getSortIcon('related_count')}
                </TableHead>
                <TableHead className="text-right">Файл</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {documents.map((doc) => (
                <TableRow key={doc.id} className={doc.is_phantom ? 'bg-orange-50' : ''}>
                  <TableCell>
                    <div className="space-y-1 max-w-md">
                      <div className="font-medium text-gray-900 text-sm flex items-center gap-2">
                        {doc.is_phantom && <Icon name="AlertCircle" size={14} className="text-orange-600" />}
                        {doc.title}
                      </div>
                      {doc.document_number && (
                        <div className="text-xs text-gray-500">№ {doc.document_number}</div>
                      )}
                      {doc.is_phantom && (
                        <div className="text-xs text-orange-600">
                          ⚠️ Файл не найден на сайте (упомянут в другом документе)
                        </div>
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
                    {formatDate(doc.published_date)}
                  </TableCell>
                  <TableCell className="text-gray-600 text-sm">
                    {formatFileSize(doc.file_size)}
                  </TableCell>
                  <TableCell className="text-center">
                    {doc.changes_count > 0 ? (
                      <Badge 
                        variant="outline" 
                        className="text-xs cursor-pointer hover:bg-primary hover:text-white transition-colors"
                        onClick={() => onViewChanges(doc.id)}
                        title="Показать изменения"
                      >
                        {doc.changes_count}
                      </Badge>
                    ) : (
                      <span className="text-gray-400 text-xs">0</span>
                    )}
                  </TableCell>
                  <TableCell className="text-center">
                    {doc.related_count > 0 ? (
                      <a 
                        href={`/versions/${doc.id}`}
                        className="inline-block"
                        title={`${doc.related_count} версий документа`}
                      >
                        <Badge 
                          variant="default"
                          className="text-xs cursor-pointer hover:bg-primary/80 transition-colors"
                        >
                          {doc.related_count}
                        </Badge>
                      </a>
                    ) : doc.prev_versions_count > 0 ? (
                      <a 
                        href={`/versions/${doc.id}`}
                        className="inline-block"
                        title={`${doc.prev_versions_count} предыдущих версий`}
                      >
                        <Badge 
                          variant="secondary"
                          className="text-xs cursor-pointer hover:bg-secondary/80 transition-colors"
                        >
                          {doc.prev_versions_count}
                        </Badge>
                      </a>
                    ) : (
                      <span className="text-gray-400 text-xs">-</span>
                    )}
                  </TableCell>
                  <TableCell className="text-right">
                    {doc.is_phantom ? (
                      <span className="text-gray-400 text-sm">—</span>
                    ) : doc.files && doc.files.length > 0 ? (
                      <div className="flex flex-col gap-1">
                        {doc.files.map((file: any, idx: number) => (
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
                              title={file.file_name}
                            >
                              <Icon name="Download" size={14} />
                              {file.file_type === 'appendix' && (
                                <span className="ml-1 text-xs">Прил.</span>
                              )}
                            </a>
                          </Button>
                        ))}
                      </div>
                    ) : (
                      <Button variant="ghost" size="sm" asChild>
                        <a 
                          href={doc.file_cdn_url || doc.url} 
                          target="_blank" 
                          rel="noopener noreferrer"
                        >
                          <Icon name="Download" size={16} />
                        </a>
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>

        <div className="flex justify-between items-center text-sm text-gray-600">
          <div>Показано {documents.length} из {total} документов</div>
          {totalPages > 1 && (
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage(page - 1)}
                disabled={page === 1}
              >
                <Icon name="ChevronLeft" size={16} />
              </Button>
              <div className="text-sm">
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
        </div>
      </CardContent>
    </Card>
  );
};

export default DocumentsTab;