#!/usr/bin/env python3
"""
Script de prueba para verificar que la API de SignaApi funciona correctamente
"""

import requests
import json
from datetime import datetime

# Configuración
API_BASE_URL = "https://signaapiv1-production.up.railway.app"

def test_health_check():
    """Probar el endpoint de health check"""
    print("🔍 Probando health check...")
    try:
        response = requests.get(f"{API_BASE_URL}/")
        print(f"✅ Status: {response.status_code}")
        print(f"✅ Response: {response.json()}")
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_cors():
    """Probar CORS"""
    print("\n🔍 Probando CORS...")
    try:
        headers = {
            'Origin': 'http://localhost:3000',
            'Access-Control-Request-Method': 'GET',
            'Access-Control-Request-Headers': 'Content-Type'
        }
        response = requests.options(f"{API_BASE_URL}/test-cors", headers=headers)
        print(f"✅ CORS Status: {response.status_code}")
        print(f"✅ CORS Headers: {dict(response.headers)}")
        return True
    except Exception as e:
        print(f"❌ CORS Error: {e}")
        return False

def test_get_doctores():
    """Probar obtener doctores"""
    print("\n🔍 Probando GET /doctores/...")
    try:
        response = requests.get(f"{API_BASE_URL}/doctores/")
        print(f"✅ Status: {response.status_code}")
        data = response.json()
        print(f"✅ Response: {json.dumps(data, indent=2)}")
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_create_doctor():
    """Probar crear un doctor"""
    print("\n🔍 Probando POST /doctores/...")
    try:
        doctor_data = {
            "nombre": "Dr. Test API",
            "email": f"test.api.{datetime.now().timestamp()}@hospital.com",
            "especialidad": "Medicina General"
        }
        
        response = requests.post(
            f"{API_BASE_URL}/doctores/",
            json=doctor_data,
            headers={'Content-Type': 'application/json'}
        )
        print(f"✅ Status: {response.status_code}")
        data = response.json()
        print(f"✅ Response: {json.dumps(data, indent=2)}")
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_get_pacientes():
    """Probar obtener pacientes"""
    print("\n🔍 Probando GET /pacientes/...")
    try:
        response = requests.get(f"{API_BASE_URL}/pacientes/")
        print(f"✅ Status: {response.status_code}")
        data = response.json()
        print(f"✅ Response: {json.dumps(data, indent=2)}")
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_create_paciente():
    """Probar crear un paciente"""
    print("\n🔍 Probando POST /pacientes/...")
    try:
        paciente_data = {
            "nombre": "Paciente Test API",
            "cedula": f"TEST{int(datetime.now().timestamp())}",
            "edad": 30
        }
        
        response = requests.post(
            f"{API_BASE_URL}/pacientes/",
            json=paciente_data,
            headers={'Content-Type': 'application/json'}
        )
        print(f"✅ Status: {response.status_code}")
        data = response.json()
        print(f"✅ Response: {json.dumps(data, indent=2)}")
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_metrics():
    """Probar endpoint de métricas"""
    print("\n🔍 Probando GET /metrics...")
    try:
        response = requests.get(f"{API_BASE_URL}/metrics")
        print(f"✅ Status: {response.status_code}")
        data = response.json()
        print(f"✅ Response: {json.dumps(data, indent=2)}")
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    """Ejecutar todas las pruebas"""
    print("🚀 Iniciando pruebas de la API de SignaApi")
    print("=" * 50)
    
    tests = [
        test_health_check,
        test_cors,
        test_get_doctores,
        test_create_doctor,
        test_get_pacientes,
        test_create_paciente,
        test_metrics
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print("-" * 30)
    
    print(f"\n📊 Resultados: {passed}/{total} pruebas pasaron")
    
    if passed == total:
        print("🎉 ¡Todas las pruebas pasaron! La API está funcionando correctamente.")
    else:
        print("⚠️ Algunas pruebas fallaron. Revisa los errores arriba.")

if __name__ == "__main__":
    main() 