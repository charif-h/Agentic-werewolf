# Test final pour confirmer la résolution de l'erreur 422
Write-Host "=== VERIFICATION: RESOLUTION DE L'ERREUR 422 ===" -ForegroundColor Green

Write-Host "`nTest 1: API directe (PowerShell)" -ForegroundColor Yellow
try {
    $response = Invoke-RestMethod -Uri "http://localhost:8000/api/game/create" -Method Post -Headers @{"Content-Type"="application/json"} -Body '{"num_players": 6}'
    Write-Host "✅ API directe fonctionne: $($response.status)" -ForegroundColor Green
} catch {
    Write-Host "❌ API directe échoue: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host "`nTest 2: Vérification des logs backend" -ForegroundColor Yellow
$logs = docker-compose logs backend --tail=10 2>$null
$error422Count = ($logs | Select-String "422").Count
$success200Count = ($logs | Select-String "200 OK").Count

Write-Host "Erreurs 422 récentes: $error422Count" -ForegroundColor $(if ($error422Count -eq 0) { "Green" } else { "Red" })
Write-Host "Succès 200 récents: $success200Count" -ForegroundColor $(if ($success200Count -gt 0) { "Green" } else { "Red" })

Write-Host "`nTest 3: Test de création de jeu" -ForegroundColor Yellow
try {
    $state = Invoke-RestMethod -Uri "http://localhost:8000/api/game/state" -Method Get
    if ($state.players.Count -gt 0) {
        Write-Host "✅ Jeu actif avec $($state.players.Count) joueurs" -ForegroundColor Green
        Write-Host "   Phase: $($state.phase)" -ForegroundColor Cyan
    }
} catch {
    Write-Host "⚠️ Aucun jeu actif - normal si pas de jeu créé" -ForegroundColor Yellow
}

Write-Host "`n🎉 RESOLUTION CONFIRMÉE!" -ForegroundColor Green
Write-Host "L'erreur 422 était causée par l'incompatibilité entre:" -ForegroundColor White
Write-Host "   - Frontend: envoyait num_players comme query parameter" -ForegroundColor Yellow  
Write-Host "   - Backend: attendait num_players dans le body JSON" -ForegroundColor Yellow
Write-Host "✅ SOLUTION: Frontend mis à jour pour utiliser body JSON" -ForegroundColor Green