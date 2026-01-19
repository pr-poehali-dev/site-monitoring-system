import { useState, useEffect, useRef } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import Icon from '@/components/ui/icon';

const API_URL = 'https://functions.poehali.dev/0d1dbd15-7762-4fb3-af49-47c960f9828b';
const LINK_FINDER_URL = 'https://functions.poehali.dev/626aeedd-c882-4ddc-902c-fe6910133d33';

interface LinkFinderResult {
  document_id: number;
  document_number?: string;
  status: string;
  references_found?: number;
  links_created?: number;
  found_documents?: Array<{
    id: number;
    number: string;
    date: string;
    title: string;
  }>;
  not_found?: string[];
  reason?: string;
  error?: string;
}

const LinkFinderPanel = () => {
  const [isRunning, setIsRunning] = useState(false);
  const [progress, setProgress] = useState(0);
  const [processed, setProcessed] = useState(0);
  const [total, setTotal] = useState(0);
  const [linksCreated, setLinksCreated] = useState(0);
  const [currentBatch, setCurrentBatch] = useState<LinkFinderResult[]>([]);
  const shouldStopRef = useRef(false);

  const getTotalDocuments = async () => {
    try {
      const response = await fetch(`${API_URL}?endpoint=stats`);
      const data = await response.json();
      console.log('Stats response:', data);
      return data.total_without_relations || 0;
    } catch (error) {
      console.error('Error getting total:', error);
      return 0;
    }
  };

  const processBatch = async (batchSize: number = 10): Promise<boolean> => {
    try {
      console.log('Processing batch, size:', batchSize);
      const response = await fetch(LINK_FINDER_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ batch_mode: true, limit: batchSize })
      });

      if (!response.ok) {
        console.error('Response not OK:', response.status);
        throw new Error(`HTTP ${response.status}`);
      }

      const data = await response.json();
      console.log('Batch response:', data);
      
      setCurrentBatch(data.results || []);
      setProcessed(prev => {
        const newProcessed = prev + (data.processed || 0);
        console.log('Processed updated:', prev, '→', newProcessed);
        return newProcessed;
      });
      
      const newLinks = (data.results || []).reduce((sum: number, r: LinkFinderResult) => 
        sum + (r.links_created || 0), 0
      );
      setLinksCreated(prev => prev + newLinks);

      return (data.processed || 0) > 0;
    } catch (error) {
      console.error('Batch processing error:', error);
      return false;
    }
  };

  const startLinkFinding = async () => {
    console.log('Starting link finding...');
    setIsRunning(true);
    shouldStopRef.current = false;
    setProcessed(0);
    setLinksCreated(0);
    setCurrentBatch([]);
    setProgress(0);

    const totalDocs = await getTotalDocuments();
    console.log('Total documents to process:', totalDocs);
    setTotal(totalDocs);

    if (totalDocs === 0) {
      console.log('No documents to process');
      setIsRunning(false);
      return;
    }

    let processedCount = 0;
    let hasMore = true;
    
    while (hasMore && !shouldStopRef.current && processedCount < totalDocs) {
      console.log('Loop iteration, processedCount:', processedCount);
      hasMore = await processBatch(10);
      processedCount += 10;
      
      const currentProgress = Math.min((processedCount / totalDocs) * 100, 100);
      console.log('Progress:', currentProgress);
      setProgress(currentProgress);

      if (hasMore && !shouldStopRef.current) {
        await new Promise(resolve => setTimeout(resolve, 500));
      }
    }

    console.log('Finished! hasMore:', hasMore, 'stopped:', shouldStopRef.current);
    setIsRunning(false);
    setProgress(100);
  };

  const stopLinkFinding = () => {
    shouldStopRef.current = true;
  };

  useEffect(() => {
    if (total > 0 && processed > 0 && isRunning) {
      const newProgress = Math.min((processed / total) * 100, 100);
      setProgress(newProgress);
    }
  }, [processed, total, isRunning]);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Icon name="Link" size={20} />
          Автоматический поиск связей
        </CardTitle>
        <CardDescription>
          Анализ содержимого документов для поиска упоминаний других постановлений
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
          <div className="flex items-start gap-3">
            <Icon name="Info" size={18} className="text-blue-600 mt-0.5" />
            <div className="space-y-1">
              <p className="text-sm font-medium text-blue-900">Как работает:</p>
              <ul className="text-xs text-blue-700 space-y-1 list-disc list-inside">
                <li>Читает первые страницы каждого документа (DOCX/PDF)</li>
                <li>Находит упоминания вида "постановление №123 от 01.02.2023"</li>
                <li>Автоматически связывает документы в цепочки версий</li>
                <li>Процесс можно остановить и продолжить позже</li>
              </ul>
            </div>
          </div>
        </div>

        {isRunning && (
          <div className="space-y-3">
            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-600">Прогресс:</span>
                <span className="font-semibold text-gray-900">
                  {processed} / {total} документов
                </span>
              </div>
              <Progress value={progress} className="h-2" />
              <div className="text-xs text-gray-500 text-center">
                {progress.toFixed(1)}%
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3 p-3 bg-gray-50 rounded-lg">
              <div className="text-center">
                <div className="text-2xl font-bold text-green-600">{linksCreated}</div>
                <div className="text-xs text-gray-600">Связей найдено</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-blue-600">{processed}</div>
                <div className="text-xs text-gray-600">Обработано</div>
              </div>
            </div>

            {currentBatch.length > 0 && (
              <div className="space-y-2 max-h-48 overflow-y-auto">
                <p className="text-xs font-semibold text-gray-700">Последняя обработка:</p>
                {currentBatch.map((result, idx) => (
                  <div key={idx} className="text-xs p-2 bg-white border rounded space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-gray-600">
                        №{result.document_number || result.document_id}
                      </span>
                      {result.status === 'success' && result.links_created! > 0 && (
                        <span className="text-green-600 font-semibold">
                          +{result.links_created} связей
                        </span>
                      )}
                      {result.status === 'success' && result.links_created === 0 && result.references_found! > 0 && (
                        <span className="text-orange-600">
                          {result.references_found} найдено, 0 связано
                        </span>
                      )}
                      {result.status === 'no_references' && (
                        <span className="text-gray-400">Нет упоминаний</span>
                      )}
                      {result.status === 'skipped' && (
                        <span className="text-yellow-600">{result.reason}</span>
                      )}
                    </div>
                    {result.not_found && result.not_found.length > 0 && (
                      <div className="text-[10px] text-orange-600 truncate">
                        Не найдено: {result.not_found.join(', ')}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        <div className="flex gap-3">
          {!isRunning ? (
            <Button 
              className="flex-1" 
              onClick={startLinkFinding}
            >
              <Icon name="Play" size={16} className="mr-2" />
              Запустить поиск связей
            </Button>
          ) : (
            <Button 
              className="flex-1" 
              variant="destructive"
              onClick={stopLinkFinding}
            >
              <Icon name="Square" size={16} className="mr-2" />
              Остановить
            </Button>
          )}
        </div>

        {!isRunning && processed > 0 && (
          <div className="p-3 bg-green-50 border border-green-200 rounded-lg">
            <div className="flex items-center gap-2">
              <Icon name="CheckCircle2" size={16} className="text-green-600" />
              <span className="text-sm font-medium text-green-900">
                Готово! Обработано {processed} документов, создано {linksCreated} связей
              </span>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default LinkFinderPanel;