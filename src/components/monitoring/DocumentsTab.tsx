import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import Icon from '@/components/ui/icon';

interface DocumentsTabProps {
  documents: any[];
  searchQuery: string;
  setSearchQuery: (value: string) => void;
  selectedSection: string;
  setSelectedSection: (value: string) => void;
  selectedYear: string;
  setSelectedYear: (value: string) => void;
  years: string[];
  sortBy: string;
  sortOrder: string;
  handleSort: (field: string) => void;
  getSortIcon: (field: string) => string | null;
  formatDate: (dateStr: string) => string;
  formatDateTime: (dateStr: string) => string;
  formatFileSize: (bytes: number) => string;
}

const DocumentsTab = ({
  documents,
  searchQuery,
  setSearchQuery,
  selectedSection,
  setSelectedSection,
  selectedYear,
  setSelectedYear,
  years,
  sortBy,
  sortOrder,
  handleSort,
  getSortIcon,
  formatDate,
  formatDateTime,
  formatFileSize
}: DocumentsTabProps) => {
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
  );
};

export default DocumentsTab;
