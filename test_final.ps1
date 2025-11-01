# Test final complet après redémarrage Docker
Write-Host "=== TEST FINAL APRÈS REDÉMARRAGE DOCKER ===" -ForegroundColor Green

# Test avec une partie très petite pour éviter les rate limits
Write-Host "`nTest avec 4 joueurs seulement..." -ForegroundColor Yellow

try {
    # Nouvelle partie avec 4 joueurs
    $createResponse = Invoke-RestMethod -Uri "http://localhost:8000/api/game/create" -Method Post -Headers @{"Content-Type"="application/json"} -Body '{"num_players": 4}'
    Write-Host "✅ Partie créée: $($createResponse.game_state.num_players) joueurs" -ForegroundColor Green
    
    # Vérifier les joueurs
    $state = Invoke-RestMethod -Uri "http://localhost:8000/api/game/state" -Method Get
    Write-Host "✅ Joueurs:" -ForegroundColor Green
    $state.players | ForEach-Object {
        $color = if ($_.role -eq "werewolf") { "Red" } else { "White" }
        Write-Host "   $($_.name): $($_.role)" -ForegroundColor $color
    }
    
    # Démarrer
    $startResponse = Invoke-RestMethod -Uri "http://localhost:8000/api/game/start" -Method Post
    Write-Host "✅ Jeu démarré: $($startResponse.announcement)" -ForegroundColor Green
    
    # Test court du cycle
    Write-Host "`nTest rapide du cycle jour/nuit..." -ForegroundColor Yellow
    
    # Nuit
    $nightResponse = Invoke-RestMethod -Uri "http://localhost:8000/api/game/next-phase" -Method Post
    Write-Host "✅ Nuit terminée" -ForegroundColor Green
    
    # Jour  
    $dayResponse = Invoke-RestMethod -Uri "http://localhost:8000/api/game/next-phase" -Method Post
    Write-Host "✅ Discussion en cours..." -ForegroundColor Green
    
    Write-Host "`n🎉 TOUS LES TESTS PASSENT!" -ForegroundColor Green
    Write-Host "Le serveur redémarré fonctionne parfaitement!" -ForegroundColor Green
    
} catch {
    Write-Host "❌ Erreur: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "❌ Détails: $($_.ErrorDetails.Message)" -ForegroundColor Red
}