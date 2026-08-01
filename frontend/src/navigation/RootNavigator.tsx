import { NavigationContainer } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import { ActivityIndicator, StyleSheet, View } from "react-native";

import { useAuth } from "../auth/AuthContext";
import { CategoryPickerScreen } from "../screens/CategoryPickerScreen";
import { DuelHistoryScreen } from "../screens/DuelHistoryScreen";
import { DuelScreen } from "../screens/DuelScreen";
import { DuelsListScreen } from "../screens/DuelsListScreen";
import { LoginScreen } from "../screens/LoginScreen";
import { NewDuelScreen } from "../screens/NewDuelScreen";
import { PlayQuestionScreen } from "../screens/PlayQuestionScreen";
import { ProfileScreen } from "../screens/ProfileScreen";
import { QuestionnaireScreen } from "../screens/QuestionnaireScreen";
import { ResearchConsentScreen } from "../screens/ResearchConsentScreen";
import { SubscriptionScreen } from "../screens/SubscriptionScreen";

export type RootStackParamList = {
  Login: undefined;
  DuelsList: undefined;
  NewDuel: undefined;
  Duel: { duelId: number };
  CategoryPicker: { duelId: number; roundSequence: number };
  PlayQuestion: { duelId: number; roundId: number; position: number };
  DuelHistory: { duelId: number };
  Profile: undefined;
  Subscription: undefined;
  ResearchConsent: undefined;
  Questionnaire: undefined;
};

const Stack = createNativeStackNavigator<RootStackParamList>();

export function RootNavigator() {
  const { account, initialising } = useAuth();

  if (initialising) {
    return (
      <View style={styles.center}>
        <ActivityIndicator />
      </View>
    );
  }

  return (
    <NavigationContainer>
      <Stack.Navigator>
        {account === null ? (
          // Everything behind the gate assumes an authenticated player, so the
          // authenticated screens are not even mounted while logged out.
          <Stack.Screen
            name="Login"
            component={LoginScreen}
            options={{ headerShown: false }}
          />
        ) : (
          <>
            <Stack.Screen
              name="DuelsList"
              component={DuelsListScreen}
              options={{ title: "Christduell" }}
            />
            <Stack.Screen
              name="NewDuel"
              component={NewDuelScreen}
              options={{ title: "Neues Duell" }}
            />
            <Stack.Screen name="Duel" component={DuelScreen} options={{ title: "Duell" }} />
            <Stack.Screen
              name="CategoryPicker"
              component={CategoryPickerScreen}
              options={{ title: "Kategorie wählen" }}
            />
            <Stack.Screen
              name="PlayQuestion"
              component={PlayQuestionScreen}
              options={{ title: "Frage" }}
            />
            <Stack.Screen
              name="DuelHistory"
              component={DuelHistoryScreen}
              options={{ title: "Verlauf" }}
            />
            <Stack.Screen
              name="Profile"
              component={ProfileScreen}
              options={{ title: "Profil" }}
            />
            <Stack.Screen
              name="Subscription"
              component={SubscriptionScreen}
              options={{ title: "Abo" }}
            />
            <Stack.Screen
              name="ResearchConsent"
              component={ResearchConsentScreen}
              options={{ title: "Forschung" }}
            />
            <Stack.Screen
              name="Questionnaire"
              component={QuestionnaireScreen}
              options={{ title: "Fragebogen" }}
            />
          </>
        )}
      </Stack.Navigator>
    </NavigationContainer>
  );
}

const styles = StyleSheet.create({
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
});
